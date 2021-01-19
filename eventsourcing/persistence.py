import json
import os
import uuid
from abc import ABC, abstractmethod
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from distutils.util import strtobool
from typing import Any, Dict, Generic, Iterator, List, Optional, Union, cast
from uuid import UUID

from eventsourcing.domain import DomainEvent, TDomainEvent
from eventsourcing.utils import get_topic, resolve_topic


class Transcoding(ABC):
    @property
    @abstractmethod
    def type(self) -> type:
        """Object type of transcoded object."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of transcoding."""

    @abstractmethod
    def encode(self, o: Any) -> Union[str, dict]:
        """Encodes given object."""

    @abstractmethod
    def decode(self, d: Union[str, dict]) -> Any:
        """Decodes encoded object."""


class AbstractTranscoder(ABC):
    @abstractmethod
    def encode(self, o: dict) -> bytes:
        """Encodes given object."""

    @abstractmethod
    def decode(self, d: bytes) -> dict:
        """Decodes encoded object."""


class Transcoder(AbstractTranscoder):
    def __init__(self):
        self.types: Dict[type, Transcoding] = {}
        self.names: Dict[str, Transcoding] = {}
        self.encoder = json.JSONEncoder(default=self._encode_obj)
        self.decoder = json.JSONDecoder(object_hook=self._decode_obj)

    def register(self, transcoding: Transcoding):
        self.types[transcoding.type] = transcoding
        self.names[transcoding.name] = transcoding

    def encode(self, o: dict) -> bytes:
        return self.encoder.encode(o).encode("utf8")

    def decode(self, d: bytes) -> dict:
        return self.decoder.decode(d.decode("utf8"))

    def _encode_obj(self, o: Any) -> Dict[str, Union[str, dict]]:
        try:
            transcoding = self.types[type(o)]
        except KeyError:
            raise TypeError(
                f"Object of type {type(o)} is not "
                "serializable. Please register a "
                "custom transcoding for this type."
            )
        else:
            return {
                "__type__": transcoding.name,
                "__data__": transcoding.encode(o),
            }

    def _decode_obj(self, d: Dict[str, Union[str, dict]]) -> Any:
        if set(d.keys()) == {
            "__type__",
            "__data__",
        }:
            t = d["__type__"]
            t = cast(str, t)
            transcoding = self.names[t]
            return transcoding.decode(d["__data__"])
        else:
            return d


class UUIDAsHex(Transcoding):
    type = UUID
    name = "uuid_hex"

    def encode(self, o: UUID) -> str:
        return o.hex

    def decode(self, d: Union[str, dict]) -> UUID:
        assert isinstance(d, str)
        return UUID(d)


class DecimalAsStr(Transcoding):
    type = Decimal
    name = "decimal_str"

    def encode(self, o: Decimal):
        return str(o)

    def decode(self, d: Union[str, dict]) -> Decimal:
        assert isinstance(d, str)
        return Decimal(d)


class DatetimeAsISO(Transcoding):
    type = datetime
    name = "datetime_iso"

    def encode(self, o: datetime) -> str:
        return o.isoformat()

    def decode(self, d: Union[str, dict]) -> datetime:
        assert isinstance(d, str)
        return datetime.fromisoformat(d)


@dataclass(frozen=True)
class StoredEvent:
    originator_id: uuid.UUID
    originator_version: int
    topic: str
    state: bytes


class Mapper(Generic[TDomainEvent]):
    def __init__(
        self,
        transcoder: AbstractTranscoder,
        compressor=None,
        cipher=None,
    ):
        self.transcoder = transcoder
        self.cipher = cipher
        self.compressor = compressor

    def from_domain_event(self, domain_event: TDomainEvent) -> StoredEvent:
        """
        Converts the given domain event to a stored event object.
        """
        topic: str = get_topic(domain_event.__class__)
        d = copy(domain_event.__dict__)
        d.pop("originator_id")
        d.pop("originator_version")
        state: bytes = self.transcoder.encode(d)
        if self.compressor:
            state = self.compressor.compress(state)
        if self.cipher:
            state = self.cipher.encrypt(state)
        return StoredEvent(
            domain_event.originator_id,
            domain_event.originator_version,
            topic,
            state,
        )

    def to_domain_event(self, stored: StoredEvent) -> TDomainEvent:
        """
        Converts the given stored event to a domain event object.
        """
        state: bytes = stored.state
        if self.cipher:
            state = self.cipher.decrypt(state)
        if self.compressor:
            state = self.compressor.decompress(state)
        d = self.transcoder.decode(state)
        d["originator_id"] = stored.originator_id
        d["originator_version"] = stored.originator_version
        cls = resolve_topic(stored.topic)
        assert issubclass(cls, DomainEvent)
        domain_event: TDomainEvent = object.__new__(cls)
        domain_event.__dict__.update(d)
        return domain_event


class OperationalError(Exception):
    pass


class RecordConflictError(Exception):
    pass


class Recorder(ABC):
    pass


class AggregateRecorder(Recorder):
    @abstractmethod
    def insert_events(
        self,
        stored_events: List[StoredEvent],
        **kwargs,
    ) -> None:
        """
        Writes stored events into database.
        """

    @abstractmethod
    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        """
        Reads stored events from database.
        """


@dataclass(frozen=True)
class Notification(StoredEvent):
    id: int


class ApplicationRecorder(AggregateRecorder):
    @abstractmethod
    def select_notifications(self, start: int, limit: int) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """

    @abstractmethod
    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """


class ProcessRecorder(ApplicationRecorder):
    @abstractmethod
    def max_tracking_id(self, application_name: str) -> int:
        pass


class EventStore(Generic[TDomainEvent]):
    """
    Stores and retrieves domain events.
    """

    def __init__(
        self,
        mapper: Mapper[TDomainEvent],
        recorder: AggregateRecorder,
    ):
        self.mapper = mapper
        self.recorder = recorder

    def put(self, events: List[TDomainEvent], **kwargs):
        """
        Stores domain events in aggregate sequence.
        """
        self.recorder.insert_events(
            list(
                map(
                    self.mapper.from_domain_event,
                    events,
                )
            ),
            **kwargs,
        )

    def get(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> Iterator[TDomainEvent]:
        """
        Retrieves domain events from aggregate sequence.
        """
        return map(
            self.mapper.to_domain_event,
            self.recorder.select_events(
                originator_id=originator_id,
                gt=gt,
                lte=lte,
                desc=desc,
                limit=limit,
            ),
        )


class InfrastructureFactory(ABC):
    TOPIC = "INFRASTRUCTURE_FACTORY"
    MAPPER_TOPIC = "MAPPER_TOPIC"
    CIPHER_TOPIC = "CIPHER_TOPIC"
    CIPHER_KEY = "CIPHER_KEY"
    COMPRESSOR_TOPIC = "COMPRESSOR_TOPIC"
    IS_SNAPSHOTTING_ENABLED = "IS_SNAPSHOTTING_ENABLED"

    @classmethod
    def construct(cls, application_name) -> "InfrastructureFactory":
        topic = os.getenv(
            cls.TOPIC,
            "eventsourcing.popo:Factory",
        )
        try:
            factory_cls = resolve_topic(topic)
        except (ModuleNotFoundError, AttributeError):
            raise EnvironmentError(
                "Failed to resolve "
                "infrastructure factory topic: "
                f"'{topic}' from environment "
                f"variable '{cls.TOPIC}'"
            )

        if not issubclass(factory_cls, InfrastructureFactory):
            raise AssertionError(f"Not an infrastructure factory: {topic}")
        return factory_cls(application_name=application_name)

    def __init__(self, application_name):
        self.application_name = application_name

    def getenv(self, key, default=None, application_name=""):
        if not application_name:
            application_name = self.application_name
        keys = [
            application_name.upper() + "_" + key,
            key,
        ]
        for key in keys:
            value = os.getenv(key)
            if value is not None:
                return value
        return default

    def mapper(
        self,
        transcoder: AbstractTranscoder,
        application_name: str = "",
    ) -> Mapper:
        cipher_topic = self.getenv(
            self.CIPHER_TOPIC,
            application_name=application_name,
        )
        cipher_key = self.getenv(
            self.CIPHER_KEY,
            application_name=application_name,
        )
        cipher = None
        compressor = None
        if cipher_topic:
            if cipher_key:
                cipher_cls = resolve_topic(cipher_topic)
                cipher = cipher_cls(cipher_key=cipher_key)
            else:
                raise EnvironmentError(
                    "Cipher key was not found in env, "
                    "although cipher topic was found"
                )
        compressor_topic = self.getenv(self.COMPRESSOR_TOPIC)
        if compressor_topic:
            compressor = resolve_topic(compressor_topic)
        return Mapper(
            transcoder=transcoder,
            cipher=cipher,
            compressor=compressor,
        )

    def event_store(self, **kwargs) -> EventStore:
        return EventStore(**kwargs)

    @abstractmethod
    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        """Constructs aggregate recorder."""

    @abstractmethod
    def application_recorder(self) -> ApplicationRecorder:
        """Constructs application recorder."""

    @abstractmethod
    def process_recorder(self) -> ProcessRecorder:
        """Constructs process recorder."""

    def is_snapshotting_enabled(self) -> bool:
        default = "no"
        return bool(
            strtobool(self.getenv(self.IS_SNAPSHOTTING_ENABLED, default) or default)
        )


@dataclass(frozen=True)
class Tracking:
    application_name: str
    notification_id: int
