import os
from abc import ABC, abstractmethod
from distutils.util import strtobool
from typing import Generic, Iterator, Optional
from uuid import UUID

from eventsourcing.domain import TDomainEvent
from eventsourcing.utils import resolve_topic
from eventsourcing.eventmapper import AbstractTranscoder, Mapper
from eventsourcing.recorders import (
    ApplicationRecorder,
    AggregateRecorder,
    ProcessRecorder,
)


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

    def put(self, events, **kwargs):
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
    TOPIC = "INFRASTRUCTURE_FACTORY_TOPIC"
    CIPHER_TOPIC = "CIPHER_TOPIC"
    CIPHER_KEY = "CIPHER_KEY"
    MAPPER_TOPIC = "MAPPER_TOPIC"
    COMPRESSOR_TOPIC = "COMPRESSOR_TOPIC"
    IS_SNAPSHOTTING_ENABLED = "IS_SNAPSHOTTING_ENABLED"

    @classmethod
    def construct(cls, name) -> "InfrastructureFactory":
        topic = os.getenv(
            cls.TOPIC,
            "eventsourcing.poporecorders:POPOInfrastructureFactory",
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

        if not issubclass(
            factory_cls, InfrastructureFactory
        ):
            raise AssertionError(
                f"Not an infrastructure factory: {topic}"
            )
        return factory_cls(application_name=name)

    def __init__(self, application_name):
        self.application_name = application_name

    def getenv(
        self, key, default=None, application_name=""
    ):
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
        compressor_topic = self.getenv(
            self.COMPRESSOR_TOPIC
        )
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
    def aggregate_recorder(self) -> AggregateRecorder:
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
            strtobool(
                self.getenv(
                    self.IS_SNAPSHOTTING_ENABLED, default
                )
                or default
            )
        )
