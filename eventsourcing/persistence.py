import json
import os
import uuid
from abc import ABC, abstractmethod
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from distutils.util import strtobool
from typing import Any, Dict, Generic, Iterator, List, Optional, Type, cast
from uuid import UUID

from eventsourcing.domain import DomainEvent, TDomainEvent
from eventsourcing.utils import get_topic, resolve_topic


class Transcoding(ABC):
    # noinspection SpellCheckingInspection
    """
    Abstract base class for custom transcodings.
    """

    @property
    @abstractmethod
    def type(self) -> type:
        # noinspection SpellCheckingInspection
        """Object type of transcoded object."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of transcoding."""

    @abstractmethod
    def encode(self, obj: Any) -> Any:
        """Encodes given object."""

    @abstractmethod
    def decode(self, data: Any) -> Any:
        """Decodes encoded object."""


class Transcoder(ABC):
    """
    Abstract base class for transcoders.
    """

    def __init__(self) -> None:
        self.types: Dict[type, Transcoding] = {}
        self.names: Dict[str, Transcoding] = {}

    def register(self, transcoding: Transcoding) -> None:
        """
        Registers given transcoding with the transcoder.
        """
        self.types[transcoding.type] = transcoding
        self.names[transcoding.name] = transcoding

    @abstractmethod
    def encode(self, obj: Any) -> bytes:
        """Encodes obj as bytes."""

    @abstractmethod
    def decode(self, data: bytes) -> Any:
        """Decodes obj from bytes."""


class JSONTranscoder(Transcoder):
    """
    Extensible transcoder that uses the Python :mod:`json` module.
    """

    def __init__(self) -> None:
        super().__init__()
        self.encoder = json.JSONEncoder(default=self._encode_obj)
        self.decoder = json.JSONDecoder(object_hook=self._decode_obj)

    def encode(self, obj: Any) -> bytes:
        """
        Encodes given object as a bytes array.
        """
        return self.encoder.encode(obj).encode("utf8")

    def decode(self, data: bytes) -> Any:
        """
        Decodes bytes array as previously encoded object.
        """
        return self.decoder.decode(data.decode("utf8"))

    def _encode_obj(self, o: Any) -> Dict[str, Any]:
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
                "_type_": transcoding.name,
                "_data_": transcoding.encode(o),
            }

    def _decode_obj(self, d: Dict[str, Any]) -> Any:
        if set(d.keys()) == {
            "_type_",
            "_data_",
        }:
            t = d["_type_"]
            t = cast(str, t)
            try:
                transcoding = self.names[t]
            except KeyError:
                raise TypeError(
                    f"Data serialized with name '{t}' is not "
                    "deserializable. Please register a "
                    "custom transcoding for this type."
                )

            return transcoding.decode(d["_data_"])
        else:
            return d


class UUIDAsHex(Transcoding):
    """
    Transcoding that represents :class:`UUID` objects as hex values.
    """

    type = UUID
    name = "uuid_hex"

    def encode(self, obj: UUID) -> str:
        return obj.hex

    def decode(self, data: str) -> UUID:
        assert isinstance(data, str)
        return UUID(data)


class DecimalAsStr(Transcoding):
    """
    Transcoding that represents :class:`Decimal` objects as strings.
    """

    type = Decimal
    name = "decimal_str"

    def encode(self, obj: Decimal) -> str:
        return str(obj)

    def decode(self, data: str) -> Decimal:
        return Decimal(data)


class DatetimeAsISO(Transcoding):
    """
    Transcoding that represents :class:`datetime` objects as ISO strings.
    """

    type = datetime
    name = "datetime_iso"

    def encode(self, obj: datetime) -> str:
        return obj.isoformat()

    def decode(self, data: str) -> datetime:
        assert isinstance(data, str)
        return datetime.fromisoformat(data)


@dataclass(frozen=True)
class StoredEvent:
    # noinspection PyUnresolvedReferences
    """
    Frozen dataclass that represents :class:`~eventsourcing.domain.DomainEvent`
    objects, such as aggregate :class:`~eventsourcing.domain.Aggregate.Event`
    objects and :class:`~eventsourcing.domain.Snapshot` objects.

    Constructor parameters:

    :param UUID originator_id: ID of the originating aggregate
    :param int originator_id: version of the originating aggregate
    :param str topic: topic of the domain event object class
    :param bytes state: serialised state of the domain event object
    """

    originator_id: uuid.UUID
    originator_version: int
    topic: str
    state: bytes


class Compressor(ABC):
    """
    Base class for compressors.
    """

    @abstractmethod
    def compress(self, data: bytes) -> bytes:
        """
        Compress bytes.
        """

    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        """
        Decompress bytes.
        """


class Cipher(ABC):
    """
    Base class for ciphers.
    """

    # noinspection PyUnusedLocal
    @abstractmethod
    def __init__(self, cipher_key: str):
        """
        Initialises cipher with given key.
        """

    @abstractmethod
    def encrypt(self, plaintext: bytes) -> bytes:
        """
        Return ciphertext for given plaintext.
        """

    @abstractmethod
    def decrypt(self, ciphertext: bytes) -> bytes:
        """
        Return plaintext for given ciphertext.
        """


class Mapper(Generic[TDomainEvent]):
    """
    Converts between domain event objects and :class:`StoredEvent` objects.

    Uses a :class:`Transcoder`, and optionally a cryptographic cipher and compressor.
    """

    def __init__(
        self,
        transcoder: Transcoder,
        compressor: Optional[Compressor] = None,
        cipher: Optional[Cipher] = None,
    ):
        self.transcoder = transcoder
        self.compressor = compressor
        self.cipher = cipher

    def from_domain_event(self, domain_event: TDomainEvent) -> StoredEvent:
        """
        Converts the given domain event to a :class:`StoredEvent` object.
        """
        topic: str = get_topic(domain_event.__class__)
        event_state = copy(domain_event.__dict__)
        originator_id = event_state.pop("originator_id")
        originator_version = event_state.pop("originator_version")
        class_version = getattr(type(domain_event), "class_version", 1)
        if class_version > 1:
            event_state["class_version"] = class_version
        stored_state: bytes = self.transcoder.encode(event_state)
        if self.compressor:
            stored_state = self.compressor.compress(stored_state)
        if self.cipher:
            stored_state = self.cipher.encrypt(stored_state)
        return StoredEvent(
            originator_id=originator_id,
            originator_version=originator_version,
            topic=topic,
            state=stored_state,
        )

    def to_domain_event(self, stored: StoredEvent) -> TDomainEvent:
        """
        Converts the given :class:`StoredEvent` to a domain event object.
        """
        stored_state: bytes = stored.state
        if self.cipher:
            stored_state = self.cipher.decrypt(stored_state)
        if self.compressor:
            stored_state = self.compressor.decompress(stored_state)
        event_state: dict = self.transcoder.decode(stored_state)
        event_state["originator_id"] = stored.originator_id
        event_state["originator_version"] = stored.originator_version
        cls = resolve_topic(stored.topic)
        assert issubclass(cls, DomainEvent)
        class_version = getattr(cls, "class_version", 1)
        from_version = event_state.pop("class_version", 1)
        while from_version < class_version:
            getattr(cls, f"upcast_v{from_version}_v{from_version + 1}")(event_state)
            from_version += 1

        domain_event = object.__new__(cls)
        domain_event.__dict__.update(event_state)
        return domain_event


class OperationalError(Exception):
    pass


class RecordConflictError(Exception):
    pass


class Recorder(ABC):
    """
    Abstract base class for stored event recorders.
    """


class AggregateRecorder(Recorder):
    """
    Abstract base class for recorders that record and
    retrieve stored events for domain model aggregates.
    """

    @abstractmethod
    def insert_events(self, stored_events: List[StoredEvent], **kwargs: Any) -> None:
        """
        Writes stored events into database.
        """

    # Todo: Change the implementations to get in batches, in case lots of events.
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
    """
    Frozen dataclass that represents domain event notifications.
    """

    id: int


class ApplicationRecorder(AggregateRecorder):
    """
    Abstract base class for recorders that record and
    retrieve stored events for domain model aggregates.

    Extends the behaviour of aggregate recorders by
    recording aggregate events in a total order that
    allows the stored events also to be retrieved
    as event notifications.
    """

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
    """
    Abstract base class for recorders that record and
    retrieve stored events for domain model aggregates.

    Extends the behaviour of applications recorders by
    recording aggregate events with tracking information
    that records the position of a processed event
    notification in a notification log.
    """

    @abstractmethod
    def max_tracking_id(self, application_name: str) -> int:
        """
        Returns the last recorded notification ID from given application.
        """


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

    def put(self, events: List[TDomainEvent], **kwargs: Any) -> None:
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
    """
    Abstract base class for infrastructure factories.
    """

    TOPIC = "INFRASTRUCTURE_FACTORY"
    MAPPER_TOPIC = "MAPPER_TOPIC"
    CIPHER_TOPIC = "CIPHER_TOPIC"
    CIPHER_KEY = "CIPHER_KEY"
    COMPRESSOR_TOPIC = "COMPRESSOR_TOPIC"
    IS_SNAPSHOTTING_ENABLED = "IS_SNAPSHOTTING_ENABLED"

    @classmethod
    def construct(cls, application_name: str = "") -> "InfrastructureFactory":
        """
        Constructs concrete infrastructure factory for given
        named application. Reads and resolves infrastructure
        factory class topic from environment variable 'INFRASTRUCTURE_FACTORY'.
        """
        # noinspection SpellCheckingInspection
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

    def __init__(self, application_name: str):
        """
        Initialises infrastructure factory object with given application name.
        """
        self.application_name = application_name

    # noinspection SpellCheckingInspection
    def getenv(
        self, key: str, default: Optional[str] = None, application_name: str = ""
    ) -> Optional[str]:
        """
        Returns value of environment variable defined by given key.
        """
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
        transcoder: Transcoder,
        application_name: str = "",
    ) -> Mapper:
        """
        Constructs a mapper.
        """
        return Mapper(
            transcoder=transcoder,
            cipher=self.cipher(application_name),
            compressor=self.compressor(application_name),
        )

    def cipher(self, application_name: str) -> Optional[Cipher]:
        """
        Reads environment variables 'CIPHER_TOPIC'
        and 'CIPHER_KEY' to decide whether or not
        to construct a cipher.
        """
        cipher_topic = self.getenv(self.CIPHER_TOPIC, application_name=application_name)
        cipher_key = self.getenv(self.CIPHER_KEY, application_name=application_name)
        cipher: Optional[Cipher] = None
        if cipher_topic:
            if cipher_key:
                cipher_cls: Type[Cipher] = resolve_topic(cipher_topic)
                cipher = cipher_cls(cipher_key=cipher_key)
            else:
                raise EnvironmentError(
                    "Cipher key was not found in env, "
                    "although cipher topic was found"
                )
        return cipher

    def compressor(self, application_name: str) -> Optional[Compressor]:
        """
        Reads environment variable 'COMPRESSOR_TOPIC' to
        decide whether or not to construct a compressor.
        """
        compressor: Optional[Compressor] = None
        compressor_topic = self.getenv(
            self.COMPRESSOR_TOPIC, application_name=application_name
        )
        if compressor_topic:
            compressor_cls: Type[Compressor] = resolve_topic(compressor_topic)
            compressor = compressor_cls()
        return compressor

    @staticmethod
    def event_store(**kwargs: Any) -> EventStore:
        """
        Constructs an event store.
        """
        return EventStore(**kwargs)

    @abstractmethod
    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        """
        Constructs an aggregate recorder.
        """

    @abstractmethod
    def application_recorder(self) -> ApplicationRecorder:
        """
        Constructs an application recorder.
        """

    @abstractmethod
    def process_recorder(self) -> ProcessRecorder:
        """
        Constructs a process recorder.
        """

    def is_snapshotting_enabled(self) -> bool:
        """
        Decides whether or not snapshotting is enabled by
        reading environment variable 'IS_SNAPSHOTTING_ENABLED'.
        Snapshotting is not enabled by default.
        """
        default = "no"
        return bool(
            strtobool(self.getenv(self.IS_SNAPSHOTTING_ENABLED, default) or default)
        )


@dataclass(frozen=True)
class Tracking:
    """
    Frozen dataclass representing the position of a domain
    event :class:`Notification` in an application's notification log.
    """

    application_name: str
    notification_id: int
