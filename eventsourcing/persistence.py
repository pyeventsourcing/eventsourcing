from __future__ import annotations

import queue
import sys
import typing
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from threading import Condition, Event, Lock, Semaphore, Thread, Timer
from time import monotonic, sleep, time
from types import GenericAlias, ModuleType, TracebackType
from typing import TYPE_CHECKING, Any, Generic, Self

from typing_extensions import TypeVar

from eventsourcing.dcb.api import DCBEvent
from eventsourcing.domain_new import (
    NIL_UUID,
    AggregateEvent,
    TaggedEvent,
    TDecision,
    WorksWithDecisions,
    null_metadata_in_context,
)
from eventsourcing.errors import (
    ConnectionNotFromPoolError,
    ConnectionPoolClosedError,
    ConnectionUnavailableError,
    DatabaseError,
    InfrastructureFactoryError,
    MapperDeserialisationError,
    ProgrammingError,
    RecordConflictError,
    WaitInterruptedError,
)
from eventsourcing.utils import (
    Environment,
    EnvType,
    TopicError,
    get_topic,
    resolve_topic,
    strtobool,
)

if TYPE_CHECKING:
    from uuid import UUID


# Backport Queue shutdown feature - remove when dropping support for Python 3.12.
_T = TypeVar("_T")
if sys.version_info[0:2] < (3, 13):  # pragma: no cover

    class ShutDown(Exception):  # noqa: N818  # pyright: ignore[reportRedeclaration]
        """Raised when put/get with shut-down queue."""

    class Queue(queue.Queue[_T]):  # pyright: ignore[reportRedeclaration]
        def __init__(self, maxsize: int = 0):
            super().__init__(maxsize)
            # Queue shutdown state
            self.is_shutdown = False

        def put(
            self,
            item: _T,
            block: bool = True,  # noqa: FBT001,FBT002
            timeout: float | None = None,
        ) -> None:
            """Put an item into the queue.

            If optional args 'block' is true and 'timeout' is None (the default),
            block if necessary until a free slot is available. If 'timeout' is
            a non-negative number, it blocks at most 'timeout' seconds and raises
            the Full exception if no free slot was available within that time.
            Otherwise ('block' is false), put an item on the queue if a free slot
            is immediately available, else raise the Full exception ('timeout'
            is ignored in that case).

            Raises ShutDown if the queue has been shut down.
            """
            with self.not_full:
                if self.is_shutdown:
                    raise ShutDown
                if self.maxsize > 0:
                    if not block:
                        if self._qsize() >= self.maxsize:
                            raise queue.Full
                    elif timeout is None:
                        while self._qsize() >= self.maxsize:
                            self.not_full.wait()
                            if self.is_shutdown:
                                raise ShutDown
                    elif timeout < 0:
                        msg = "'timeout' must be a non-negative number"
                        raise ValueError(msg)
                    else:
                        endtime = time() + timeout
                        while self._qsize() >= self.maxsize:
                            remaining = endtime - time()
                            if remaining <= 0.0:
                                raise queue.Full
                            self.not_full.wait(remaining)
                            if self.is_shutdown:
                                raise ShutDown
                self._put(item)
                self.unfinished_tasks += 1
                self.not_empty.notify()

        def get(
            self,
            block: bool = True,  # noqa: FBT001,FBT002
            timeout: float | None = None,
        ) -> _T:
            """Remove and return an item from the queue.

            If optional args 'block' is true and 'timeout' is None (the default),
            block if necessary until an item is available. If 'timeout' is
            a non-negative number, it blocks at most 'timeout' seconds and raises
            the Empty exception if no item was available within that time.
            Otherwise ('block' is false), return an item if one is immediately
            available, else raise the Empty exception ('timeout' is ignored
            in that case).

            Raises ShutDown if the queue has been shut down and is empty,
            or if the queue has been shut down immediately.
            """
            with self.not_empty:
                if self.is_shutdown and not self._qsize():
                    raise ShutDown
                if not block:
                    if not self._qsize():
                        raise queue.Empty
                elif timeout is None:
                    while not self._qsize():
                        self.not_empty.wait()
                        if self.is_shutdown and not self._qsize():
                            raise ShutDown
                elif timeout < 0:
                    msg = "'timeout' must be a non-negative number"
                    raise ValueError(msg)
                else:
                    endtime = time() + timeout
                    while not self._qsize():
                        remaining = endtime - time()
                        if remaining <= 0.0:
                            raise queue.Empty
                        self.not_empty.wait(remaining)
                        if self.is_shutdown and not self._qsize():
                            raise ShutDown
                item = self._get()
                self.not_full.notify()
                return item

        def shutdown(
            self,
            immediate: bool = False,  # noqa: FBT001,FBT002
        ) -> None:
            """Shut-down the queue, making queue gets and puts raise ShutDown.

            By default, gets will only raise once the queue is empty. Set
            'immediate' to True to make gets raise immediately instead.

            All blocked callers of put() and get() will be unblocked. If
            'immediate', a task is marked as done for each item remaining in
            the queue, which may unblock callers of join().
            """
            with self.mutex:
                self.is_shutdown = True
                if immediate:
                    while self._qsize():
                        self._get()
                        if self.unfinished_tasks > 0:
                            self.unfinished_tasks -= 1
                    # release all blocked threads in `join()`
                    self.all_tasks_done.notify_all()
                # All getters need to re-check queue-empty to raise ShutDown
                self.not_empty.notify_all()
                self.not_full.notify_all()

else:  # pragma: no cover
    Queue = queue.Queue  # pyright: ignore[reportAssignmentType]
    ShutDown = queue.ShutDown  # pyright: ignore[reportAttributeAccessIssue]


class Transcoder(ABC, WorksWithDecisions[TDecision]):
    """Abstract base class for transcoders."""

    @abstractmethod
    def encode(self, decision: TDecision) -> bytes:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def decode(self, data: bytes, decision_class: type[TDecision]) -> TDecision:
        raise NotImplementedError  # pragma: no cover


@dataclass(frozen=True, kw_only=True)
class StoredEvent:
    """Frozen dataclass that represents :class:`~eventsourcing.domain.DomainEvent`
    objects, such as aggregate :class:`~eventsourcing.domain.Aggregate.Event`
    objects and :class:`~eventsourcing.domain.Snapshot` objects.
    """

    originator_id: str
    """ID of the originating aggregate."""
    originator_version: int
    """Position in an aggregate sequence."""
    topic: str
    """Topic of a domain event object class."""
    state: bytes
    """Serialised state of a domain event object."""
    uuid: UUID = NIL_UUID
    """Optional event ID."""
    metadata: dict[str, str] = field(default_factory=dict)
    """Serialised metadata."""


class Compressor(ABC):
    """Base class for compressors."""

    @abstractmethod
    def compress(self, data: bytes) -> bytes:
        """Compress bytes."""

    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        """Decompress bytes."""


class Cipher(ABC):
    """Base class for ciphers."""

    @abstractmethod
    def __init__(self, environment: Environment):
        """Initialises cipher with given environment."""

    @abstractmethod
    def encrypt(self, plaintext: bytes) -> bytes:
        """Return ciphertext for given plaintext."""

    @abstractmethod
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Return plaintext for given ciphertext."""


class Mapper(ABC, Generic[TDecision]):
    """
    Abstract base class for converting between domain event
    objects and :class:`StoredEvent` objects.
    """

    def __init__(
        self,
        transcoder: Transcoder[TDecision],
        compressor: Compressor | None = None,
        cipher: Cipher | None = None,
    ):
        self.transcoder = transcoder
        self.compressor = compressor
        self.cipher = cipher

    @abstractmethod
    def to_stored_event(self, domain_event: AggregateEvent[TDecision]) -> StoredEvent:
        """Converts the given domain event to a :class:`StoredEvent` object."""

    @abstractmethod
    def to_domain_event(self, stored_event: StoredEvent) -> AggregateEvent[TDecision]:
        """Converts the given :class:`StoredEvent` to a domain event object."""


# # TODO: Eliminate this by adjusting JSONTranscoder to extract 'event_state' dict
# #  (`event_state = dict(vars(domain_event.decision))`) and reconstructing Decision
# #  class.
# class DataclassMapper(Mapper):
#     """Converts between dataclass domain event objects and :class:`StoredEvent` object
#     s.
#
#     Uses a :class:`Transcoder`, and optionally a cryptographic cipher and compressor.
#     """
#
#     def to_stored_event(self, domain_event: AggregateEvent[TDecision]) -> StoredEvent:
#         topic = get_topic(domain_event.decision.__class__)
#         event_state = dict(vars(domain_event.decision))
#         # originator_id = event_state.pop("originator_id")
#         # originator_version = event_state.pop("originator_version")
#         class_version = getattr(type(domain_event.decision), "class_version", 1)
#         if class_version > 1:
#             event_state["class_version"] = class_version
#         stored_state = self.transcoder.encode(event_state)
#         if self.compressor:
#             stored_state = self.compressor.compress(stored_state)
#         if self.cipher:
#             stored_state = self.cipher.encrypt(stored_state)
#         return StoredEvent(
#             originator_id=domain_event.originator_id,
#             originator_version=domain_event.originator_version,
#             topic=topic,
#             state=stored_state,
#             metadata=domain_event.metadata,
#             uuid=domain_event.uuid,
#         )
#
#     def to_domain_event(self, stored_event: StoredEvent) -> AggregateEvent[TDecision]:
#         """Converts the given :class:`StoredEvent` to a domain event object."""
#         cls = resolve_topic(stored_event.topic)
#
#         stored_state = stored_event.state
#         try:
#             if self.cipher:
#                 stored_state = self.cipher.decrypt(stored_state)
#             if self.compressor:
#                 stored_state = self.compressor.decompress(stored_state)
#             event_state: dict[str, Any] = self.transcoder.decode(stored_state, cls)
#         except Exception as e:
#             msg = (
#                 f"Failed to deserialise state of stored event with "
#                 f"topic '{stored_event.topic}', "
#                 f"originator_id '{stored_event.originator_id}' and "
#                 f"originator_version {stored_event.originator_version}: {e}"
#             )
#             raise MapperDeserialisationError(msg) from e
#
#         # Support legacy data by supplementing domain event metadata
#         # from separately stored event metadata.
#         # # TODO: Also maybe store metadata separately from domain event as config opt
#          ion?
#         # stored_metadata = stored_event.metadata
#         # event_metadata = event_state.get("metadata")
#         # if isinstance(stored_metadata, dict) and isinstance(event_metadata, dict):
#         #     for key, value in stored_metadata.items():
#         #         if key not in event_metadata:
#         #             event_metadata[key] = value
#
#         # if "event_id" not in event_state and stored_event.event_id:
#         #     event_state["event_id"] = stored_event.event_id
#         class_version = getattr(cls, "class_version", 1)
#         from_version = event_state.pop("class_version", 1)
#         while from_version < class_version:
#             getattr(cls, f"upcast_v{from_version}_v{from_version + 1}")(event_state)
#             from_version += 1
#         decision = cls(**event_state)
#         return AggregateEvent(
#             decision=decision,
#             uuid=stored_event.uuid,
#             metadata=stored_event.metadata,
#             originator_id=stored_event.originator_id,
#             originator_version=stored_event.originator_version,
#         )


class IntegrityError(DatabaseError, RecordConflictError):
    """Exception raised when the relational integrity of the
    database is affected, e.g. a foreign key check fails.
    """


class InternalError(DatabaseError):
    """Exception raised when the database encounters an internal
    error, e.g. the cursor is not valid anymore, the transaction
    is out of sync, etc.
    """


class Recorder:
    pass


class AggregateRecorder(Recorder, ABC):
    """Abstract base class for inserting and selecting stored events."""

    @abstractmethod
    def insert_events(
        self, stored_events: Sequence[StoredEvent], **kwargs: Any
    ) -> Sequence[int] | None:
        """Writes stored events into database."""

    @abstractmethod
    def select_events(
        self,
        originator_id: str,
        *,
        gt: int | None = None,
        lte: int | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> Sequence[StoredEvent]:
        """Reads stored events from database."""


@dataclass(frozen=True, kw_only=True)
class Notification(StoredEvent):
    """Frozen dataclass that represents domain event notifications."""

    id: int
    """Position in an application sequence."""


class ApplicationRecorder(AggregateRecorder):
    """Abstract base class for recording events in both aggregate
    and application sequences.
    """

    @abstractmethod
    def select_notifications(
        self,
        start: int | None,
        limit: int,
        stop: int | None = None,
        topics: Sequence[str] = (),
        *,
        inclusive_of_start: bool = True,
    ) -> Sequence[Notification]:
        """Returns a list of Notification objects representing events from an
        application sequence. If `inclusive_of_start` is True (the default),
        the returned Notification objects will have IDs greater than or equal
        to `start` and less than or equal to `stop`. If `inclusive_of_start`
        is False, the Notification objects will have IDs greater than `start`
        and less than or equal to `stop`.
        """

    @abstractmethod
    def max_notification_id(self) -> int | None:
        """Returns the largest notification ID in an application sequence,
        or None if no stored events have been recorded.
        """

    @abstractmethod
    def subscribe(
        self, gt: int | None = None, topics: Sequence[str] = ()
    ) -> Subscription[ApplicationRecorder]:
        """Returns an iterator of Notification objects representing events from an
        application sequence.

        The iterator will block after the last recorded event has been yielded, but
        will then continue yielding newly recorded events when they are recorded.

        Notifications will have IDs greater than the optional `gt` argument.
        """


class TrackingRecorder(Recorder, ABC):
    """Abstract base class for recorders that record tracking
    objects atomically with other state.
    """

    @abstractmethod
    def insert_tracking(self, tracking: Tracking) -> None:
        """Records a tracking object."""

    @abstractmethod
    def max_tracking_id(self, application_name: str) -> int | None:
        """Returns the largest notification ID across all recorded tracking objects
        for the named application, or None if no tracking objects have been recorded.
        """

    def has_tracking_id(
        self, application_name: str, notification_id: int | None
    ) -> bool:
        """Returns True if given notification_id is None or a tracking
        object with the given application_name and a notification ID greater
        than or equal to the given notification_id has been recorded.
        """
        if notification_id is None:
            return True
        max_tracking_id = self.max_tracking_id(application_name)
        return max_tracking_id is not None and max_tracking_id >= notification_id

    def wait(
        self,
        application_name: str,
        notification_id: int | None,
        timeout: float = 1.0,
        interrupt: Event | None = None,
    ) -> None:
        """Block until a tracking object with the given application name and a
        notification ID greater than equal to the given value has been recorded.

        Polls max_tracking_id() with exponential backoff until the timeout
        is reached, or until the optional interrupt event is set.

        The timeout argument should be a floating point number specifying a
        timeout for the operation in seconds (or fractions thereof). The default
        is 1.0 seconds.

        Raises TimeoutError if the timeout is reached.

        Raises WaitInterruptError if the `interrupt` is set before `timeout` is reached.
        """
        deadline = monotonic() + timeout
        sleep_interval_ms = 100.0
        max_sleep_interval_ms = 800.0
        while True:
            if self.has_tracking_id(application_name, notification_id):
                break
            if interrupt:
                if interrupt.wait(timeout=sleep_interval_ms / 1000):
                    raise WaitInterruptedError
            else:
                sleep(sleep_interval_ms / 1000)
            remaining = deadline - monotonic()
            if remaining < 0:
                msg = (
                    f"Timed out waiting for notification {notification_id} "
                    f"from application '{application_name}' to be processed"
                )
                raise TimeoutError(msg)
            sleep_interval_ms = min(
                sleep_interval_ms * 2, remaining * 1000, max_sleep_interval_ms
            )


class ProcessRecorder(TrackingRecorder, ApplicationRecorder, ABC):
    pass


@dataclass(frozen=True)
class Recording(Generic[TDecision]):
    """Represents the recording of a domain event."""

    domain_event: AggregateEvent[TDecision]
    """The domain event that has been recorded."""
    notification: Notification
    """A Notification that represents the domain event in the application sequence."""


class EventStore(Generic[TDecision]):
    """Stores and retrieves domain events."""

    def __init__(
        self,
        mapper: Mapper[TDecision],
        recorder: AggregateRecorder,
    ):
        self.mapper = mapper
        self.recorder = recorder

    def put(
        self, domain_events: Sequence[AggregateEvent[TDecision]], **kwargs: Any
    ) -> list[Recording[TDecision]]:
        """Stores domain events in aggregate sequence."""
        stored_events = list(map(self.mapper.to_stored_event, domain_events))
        recordings = []
        notification_ids = self.recorder.insert_events(stored_events, **kwargs)
        if notification_ids:
            assert len(notification_ids) == len(stored_events)
            for d, s, n_id in zip(
                domain_events, stored_events, notification_ids, strict=True
            ):
                recordings.append(
                    Recording(
                        d,
                        Notification(
                            originator_id=s.originator_id,
                            originator_version=s.originator_version,
                            topic=s.topic,
                            state=s.state,
                            id=n_id,
                        ),
                    )
                )
        return recordings

    def get(
        self,
        originator_id: str,
        *,
        gt: int | None = None,
        lte: int | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> Iterator[AggregateEvent[TDecision]]:
        """Retrieves domain events from aggregate sequence."""
        with null_metadata_in_context():
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


TTrackingRecorder = TypeVar("TTrackingRecorder", bound=TrackingRecorder)


class BaseInfrastructureFactory(ABC, Generic[TTrackingRecorder]):
    """Abstract base class for infrastructure factories."""

    PERSISTENCE_MODULE = "PERSISTENCE_MODULE"
    TRANSCODER_TOPIC = "TRANSCODER_TOPIC"
    CIPHER_TOPIC = "CIPHER_TOPIC"
    COMPRESSOR_TOPIC = "COMPRESSOR_TOPIC"

    def __init__(self, env: Environment | EnvType | None):
        """Initialises infrastructure factory object with given application name."""
        self.env = env if isinstance(env, Environment) else Environment(env=env)
        self._is_entered = False

    @property
    def is_entered(self) -> bool:
        return self._is_entered

    def __enter__(self) -> Self:
        self._is_entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._is_entered = False

    def close(self) -> None:
        """Closes any database connections, and anything else that needs closing."""

    @classmethod
    def construct(
        cls: type[Self],
        env: Environment | EnvType | None = None,
    ) -> Self:
        """Constructs concrete infrastructure factory for given
        named application. Reads and resolves persistence
        topic from environment variable 'PERSISTENCE_MODULE'.
        """
        factory_cls: type
        if env is None:
            env = Environment()
        elif not isinstance(env, Environment):
            env = Environment(env=env)
        topic = (
            env.get(
                cls.PERSISTENCE_MODULE,
                "",
            )
            or "eventsourcing.popo"
        )
        try:
            obj: Any = resolve_topic(topic)
        except TopicError as e:
            msg = (
                "Failed to resolve persistence module topic: "
                f"'{topic}' from environment "
                f"variable '{cls.PERSISTENCE_MODULE}'"
            )
            raise InfrastructureFactoryError(msg) from e

        if isinstance(obj, ModuleType):
            # Find the factory in the module.
            factory_classes = set[type[Any]]()
            for member in obj.__dict__.values():
                # Look for classes...
                if not isinstance(member, type):
                    continue
                # Issue with Python 3.9 and 3.10.
                if isinstance(member, GenericAlias):
                    continue  # pragma: no cover (for Python > 3.10 only)
                if not issubclass(member, cls):
                    continue
                if getattr(member, "__parameters__", None):
                    continue
                factory_classes.add(member)

            if len(factory_classes) == 1:
                factory_cls = next(iter(factory_classes))
            else:
                msg = (
                    f"Found {len(factory_classes)} infrastructure factory classes in"
                    f" '{topic}', expected 1."
                )
                raise InfrastructureFactoryError(msg)
        elif isinstance(obj, type) and issubclass(obj, cls):
            factory_cls = obj
        else:
            msg = (
                f"Topic '{topic}' didn't resolve to a persistence module "
                f"or infrastructure factory class: {obj}"
            )
            raise InfrastructureFactoryError(msg)
        return factory_cls(env=env)

    def transcoder(
        self,
    ) -> Transcoder[TDecision]:
        """Constructs a transcoder."""
        transcoder_topic = self.env.get(self.TRANSCODER_TOPIC)
        if transcoder_topic:
            transcoder_class: type[Transcoder[TDecision]] = resolve_topic(
                transcoder_topic
            )
        else:
            msg = f"Please set {self.TRANSCODER_TOPIC} in application environment"
            raise ProgrammingError(msg)
        return transcoder_class()

    def cipher(self) -> Cipher | None:
        """Reads environment variables 'CIPHER_TOPIC'
        and 'CIPHER_KEY' to decide whether or not
        to construct a cipher.
        """
        cipher_topic = self.env.get(self.CIPHER_TOPIC)
        cipher: Cipher | None = None
        default_cipher_topic = "eventsourcing.cipher:AESCipher"
        if self.env.get("CIPHER_KEY") and not cipher_topic:
            cipher_topic = default_cipher_topic

        if cipher_topic:
            cipher_cls: type[Cipher] = resolve_topic(cipher_topic)
            cipher = cipher_cls(self.env)

        return cipher

    def compressor(self) -> Compressor | None:
        """Reads environment variable 'COMPRESSOR_TOPIC' to
        decide whether or not to construct a compressor.
        """
        compressor: Compressor | None = None
        compressor_topic = self.env.get(self.COMPRESSOR_TOPIC)
        if compressor_topic:
            compressor_cls: type[Compressor] | Compressor = resolve_topic(
                compressor_topic
            )
            if isinstance(compressor_cls, type):
                compressor = compressor_cls()
            else:
                compressor = compressor_cls
        return compressor


class InfrastructureFactory(BaseInfrastructureFactory[TTrackingRecorder]):
    """Abstract base class for Application factories."""

    MAPPER_TOPIC = "MAPPER_TOPIC"
    IS_SNAPSHOTTING_ENABLED = "IS_SNAPSHOTTING_ENABLED"
    APPLICATION_RECORDER_TOPIC = "APPLICATION_RECORDER_TOPIC"
    TRACKING_RECORDER_TOPIC = "TRACKING_RECORDER_TOPIC"
    PROCESS_RECORDER_TOPIC = "PROCESS_RECORDER_TOPIC"

    def mapper(
        self,
        transcoder: Transcoder[TDecision] | None = None,
        mapper_class: type[Mapper[TDecision]] | None = None,
    ) -> Mapper[TDecision]:
        """Constructs a mapper."""
        # Resolve MAPPER_TOPIC if no given class.
        if mapper_class is None:
            mapper_topic = self.env.get(self.MAPPER_TOPIC)
            mapper_class = (
                resolve_topic(mapper_topic)
                if mapper_topic
                else AggregateEventMapper[TDecision]
            )

        # Check we have a mapper class.
        assert mapper_class is not None
        origin_mapper_class = typing.get_origin(mapper_class) or mapper_class
        assert isinstance(origin_mapper_class, type), mapper_class
        assert issubclass(origin_mapper_class, Mapper), mapper_class

        # Construct and return a mapper.
        return mapper_class(
            transcoder=transcoder or self.transcoder(),
            cipher=self.cipher(),
            compressor=self.compressor(),
        )

    def event_store(
        self,
        mapper: Mapper[TDecision] | None = None,
        recorder: AggregateRecorder | None = None,
    ) -> EventStore[TDecision]:
        """Constructs an event store."""
        return EventStore(
            mapper=mapper or self.mapper(),
            recorder=recorder or self.application_recorder(),
        )

    @abstractmethod
    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        """Constructs an aggregate recorder."""

    @abstractmethod
    def application_recorder(self) -> ApplicationRecorder:
        """Constructs an application recorder."""

    @abstractmethod
    def tracking_recorder(
        self, tracking_recorder_class: type[TTrackingRecorder] | None = None
    ) -> TTrackingRecorder:
        """Constructs a tracking recorder."""

    @abstractmethod
    def process_recorder(self) -> ProcessRecorder:
        """Constructs a process recorder."""

    def is_snapshotting_enabled(self) -> bool:
        """Decides whether or not snapshotting is enabled by
        reading environment variable 'IS_SNAPSHOTTING_ENABLED'.
        Snapshotting is not enabled by default.
        """
        return strtobool(self.env.get(self.IS_SNAPSHOTTING_ENABLED, "no"))


@dataclass(frozen=True)
class Tracking:
    """Frozen dataclass representing the position of a domain
    event :class:`Notification` in an application's notification log.
    """

    application_name: str
    notification_id: int


Params = Sequence[Any] | Mapping[str, Any]


class Cursor(ABC):
    @abstractmethod
    def execute(self, statement: str | bytes, params: Params | None = None) -> None:
        """Executes given statement."""

    @abstractmethod
    def fetchall(self) -> Any:
        """Fetches all results."""

    @abstractmethod
    def fetchone(self) -> Any:
        """Fetches one result."""


TCursor = TypeVar("TCursor", bound=Cursor)


class Connection(ABC, Generic[TCursor]):
    def __init__(self, max_age: float | None = None) -> None:
        self._closed = False
        self._closing = Event()
        self._close_lock = Lock()
        self.in_use = Lock()
        self.in_use.acquire()
        if max_age is not None:
            self._max_age_timer: Timer | None = Timer(
                interval=max_age,
                function=self._close_when_not_in_use,
            )
            self._max_age_timer.daemon = True
            self._max_age_timer.start()
        else:
            self._max_age_timer = None
        self.is_writer: bool | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def closing(self) -> bool:
        return self._closing.is_set()

    @abstractmethod
    def commit(self) -> None:
        """Commits transaction."""

    @abstractmethod
    def rollback(self) -> None:
        """Rolls back transaction."""

    @abstractmethod
    def cursor(self) -> TCursor:
        """Creates new cursor."""

    def close(self) -> None:
        with self._close_lock:
            self._close()

    @abstractmethod
    def _close(self) -> None:
        self._closed = True
        if self._max_age_timer:
            self._max_age_timer.cancel()

    def _close_when_not_in_use(self) -> None:
        self._closing.set()
        with self.in_use:
            if not self._closed:
                self.close()


TConnection = TypeVar("TConnection", bound=Connection[Any])


class ConnectionPool(ABC, Generic[TConnection]):
    def __init__(
        self,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: float = 30.0,
        max_age: float | None = None,
        pre_ping: bool = False,
        mutually_exclusive_read_write: bool = False,
    ) -> None:
        """Initialises a new connection pool.

        The 'pool_size' argument specifies the maximum number of connections
        that will be put into the pool when connections are returned. The
        default value is 5

        The 'max_overflow' argument specifies the additional number of
        connections that can be issued by the pool, above the 'pool_size'.
        The default value is 10.

        The 'pool_timeout' argument specifies the maximum time in seconds
        to keep requests for connections waiting. Connections are kept
        waiting if the number of connections currently in use is not less
        than the sum of 'pool_size' and 'max_overflow'. The default value
        is 30.0

        The 'max_age' argument specifies the time in seconds until a
        connection will automatically be closed. Connections are only closed
        in this way after are not in use. Connections that are in use will
        not be closed automatically. The default value in None, meaning
        connections will not be automatically closed in this way.

        The 'mutually_exclusive_read_write' argument specifies whether
        requests for connections for writing whilst connections for reading
        are in use. It also specifies whether requests for connections for reading
        will be kept waiting whilst a connection for writing is in use. The default
        value is false, meaning reading and writing will not be mutually exclusive
        in this way.
        """
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.max_age = max_age
        self.pre_ping = pre_ping
        self._pool: deque[TConnection] = deque()
        self._in_use: dict[int, TConnection] = {}
        self._get_semaphore = Semaphore()
        self._put_condition = Condition()
        self._no_readers = Condition()
        self._num_readers: int = 0
        self._writer_lock = Lock()
        self._num_writers: int = 0
        self._mutually_exclusive_read_write = mutually_exclusive_read_write
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def num_in_use(self) -> int:
        """Indicates the total number of connections currently in use."""
        with self._put_condition:
            return self._num_in_use

    @property
    def _num_in_use(self) -> int:
        return len(self._in_use)

    @property
    def num_in_pool(self) -> int:
        """Indicates the number of connections currently in the pool."""
        with self._put_condition:
            return self._num_in_pool

    @property
    def _num_in_pool(self) -> int:
        return len(self._pool)

    @property
    def _is_pool_full(self) -> bool:
        return self._num_in_pool >= self.pool_size

    @property
    def _is_use_full(self) -> bool:
        return self._num_in_use >= self.pool_size + self.max_overflow

    def get_connection(
        self, timeout: float | None = None, *, is_writer: bool | None = None
    ) -> TConnection:
        """Issues connections, or raises ConnectionPoolExhausted error.
        Provides "fairness" on attempts to get connections, meaning that
        connections are issued in the same order as they are requested.

        The 'timeout' argument overrides the timeout specified
        by the constructor argument 'pool_timeout'. The default
        value is None, meaning the 'pool_timeout' argument will
        not be overridden.

        The optional 'is_writer' argument can be used to request
        a connection for writing (true), and request a connection
        for reading (false). If the value of this argument is None,
        which is the default, the writing and reading interlocking
        mechanism is not activated. Only one connection for writing
        will be issued, which means requests for connections for
        writing are kept waiting whilst another connection for writing
        is in use.

        If reading and writing are mutually exclusive, requsts for
        connections for writing are kept waiting whilst connections
        for reading are in use, and requests for connections for reading
        are kept waiting whilst a connection for writing is in use.
        """
        # Make sure we aren't dealing with a closed pool.
        if self._closed:
            raise ConnectionPoolClosedError

        # Decide the timeout for getting a connection.
        timeout = self.pool_timeout if timeout is None else timeout

        # Remember when we started trying to get a connection.
        started = time()

        # Join queue of threads waiting to get a connection ("fairness").
        if self._get_semaphore.acquire(timeout=timeout):
            try:
                # If connection is for writing, get write lock and wait for no readers.
                if is_writer is True:
                    if not self._writer_lock.acquire(
                        timeout=self._time_remaining(timeout, started)
                    ):
                        msg = "Timed out waiting for return of writer"
                        raise ConnectionUnavailableError(msg)
                    if self._mutually_exclusive_read_write:
                        with self._no_readers:
                            if self._num_readers > 0 and not self._no_readers.wait(
                                timeout=self._time_remaining(timeout, started)
                            ):
                                self._writer_lock.release()
                                msg = "Timed out waiting for return of reader"
                                raise ConnectionUnavailableError(msg)
                    self._num_writers += 1

                # If connection is for reading, and writing excludes reading,
                # then wait for the writer lock, and increment number of readers.
                elif is_writer is False:
                    if self._mutually_exclusive_read_write:
                        if not self._writer_lock.acquire(
                            timeout=self._time_remaining(timeout, started)
                        ):
                            msg = "Timed out waiting for return of writer"
                            raise ConnectionUnavailableError(msg)
                        self._writer_lock.release()
                    with self._no_readers:
                        self._num_readers += 1

                # Actually try to get a connection withing the time remaining.
                conn = self._get_connection(
                    timeout=self._time_remaining(timeout, started)
                )

                # Remember if this connection is for reading or writing.
                conn.is_writer = is_writer

                # Return the connection.
                return conn
            finally:
                self._get_semaphore.release()
        else:
            # Timed out waiting for semaphore.
            msg = "Timed out waiting for connection pool semaphore"
            raise ConnectionUnavailableError(msg)

    def _get_connection(self, timeout: float = 0.0) -> TConnection:
        """Gets or creates connections from pool within given
        time, otherwise raises a "pool exhausted" error.

        Waits for connections to be returned if the pool
        is fully used. And optionally ensures a connection
        is usable before returning a connection for use.

        Tracks use of connections, and number of readers.
        """
        started = time()
        # Get lock on tracking usage of connections.
        with self._put_condition:
            # Try to get a connection from the pool.
            try:
                conn = self._pool.popleft()
            except IndexError:
                # Pool is empty, but are connections fully used?
                if self._is_use_full:
                    # Fully used, so wait for a connection to be returned.
                    if self._put_condition.wait(
                        timeout=self._time_remaining(timeout, started)
                    ):
                        # Connection has been returned, so try again.
                        return self._get_connection(
                            timeout=self._time_remaining(timeout, started)
                        )
                    # Timed out waiting for a connection to be returned.
                    msg = "Timed out waiting for return of connection"
                    raise ConnectionUnavailableError(msg) from None
                # Not fully used, so create a new connection.
                conn = self._create_connection()
                # print("created another connection")

                # Connection should be pre-locked for use (avoids timer race).
                assert conn.in_use.locked()

            else:
                # Got unused connection from pool, so lock for use.
                conn.in_use.acquire()

                # Check the connection wasn't closed by the timer.
                if conn.closed:
                    return self._get_connection(
                        timeout=self._time_remaining(timeout, started)
                    )

                # Check the connection is actually usable.
                if self.pre_ping:
                    try:
                        conn.cursor().execute("SELECT 1")
                    except Exception:
                        # Probably connection is closed on server,
                        # but just try to make sure it is closed.
                        conn.close()

                        # Try again to get a connection.
                        return self._get_connection(
                            timeout=self._time_remaining(timeout, started)
                        )

            # Track the connection is now being used.
            self._in_use[id(conn)] = conn

            # Return the connection.
            return conn

    def put_connection(self, conn: TConnection) -> None:
        """Returns connections to the pool, or closes connection
        if the pool is full.

        Unlocks write lock after writer has returned, and
        updates count of readers when readers are returned.

        Notifies waiters when connections have been returned,
        and when there are no longer any readers.
        """
        # Start forgetting if this connection was for reading or writing.
        is_writer, conn.is_writer = conn.is_writer, None

        # Get a lock on tracking usage of connections.
        with self._put_condition:
            # Make sure we aren't dealing with a closed pool
            if self._closed:
                msg = "Pool is closed"
                raise ConnectionPoolClosedError(msg)

            # Make sure we are dealing with a connection from this pool.
            try:
                del self._in_use[id(conn)]
            except KeyError:
                msg = "Connection not in use in this pool"
                raise ConnectionNotFromPoolError(msg) from None

            if not conn.closed:
                # Put open connection in pool if not full.
                if not conn.closing and not self._is_pool_full:
                    self._pool.append(conn)
                    # Close open connection if the pool is full or timer has fired.
                else:
                    # Otherwise, close the connection.
                    conn.close()

            # Unlock the connection for subsequent use (and for closing by the timer).
            conn.in_use.release()

            # If the connection was for writing, unlock the writer lock.
            if is_writer is True:
                self._num_writers -= 1
                self._writer_lock.release()

            # Or if it was for reading, decrement the number of readers.
            elif is_writer is False:
                with self._no_readers:
                    self._num_readers -= 1
                    if self._num_readers == 0 and self._mutually_exclusive_read_write:
                        self._no_readers.notify()

            # Notify a thread that is waiting for a connection to be returned.
            self._put_condition.notify()

    @abstractmethod
    def _create_connection(self) -> TConnection:
        """Create a new connection.

        Subclasses should implement this method by
        creating a database connection of the type
        being pooled.
        """

    def close(self) -> None:
        """Close the connection pool."""
        with self._put_condition:
            if self._closed:
                return
            for conn in self._in_use.values():
                conn.close()
            while True:
                try:
                    conn = self._pool.popleft()
                except IndexError:
                    break
                else:
                    conn.close()
            self._closed = True

    @staticmethod
    def _time_remaining(timeout: float, started: float) -> float:
        return max(0.0, timeout + started - time())

    def __del__(self) -> None:
        self.close()


TApplicationRecorder_co = TypeVar(
    "TApplicationRecorder_co", bound=ApplicationRecorder, covariant=True
)


class Subscription(Iterator[Notification], Generic[TApplicationRecorder_co]):
    def __init__(
        self,
        recorder: TApplicationRecorder_co,
        gt: int | None = None,
        topics: Sequence[str] = (),
    ) -> None:
        self._recorder = recorder
        self._last_notification_id = gt
        self._topics = topics
        self._has_been_entered = False
        self._has_been_stopped = False

    def __enter__(self) -> Self:
        if self._has_been_entered:
            msg = "Already entered subscription context manager"
            raise ProgrammingError(msg)
        self._has_been_entered = True
        return self

    def __exit__(self, *args: object, **kwargs: Any) -> None:
        if not self._has_been_entered:
            msg = "Not already entered subscription context manager"
            raise ProgrammingError(msg)
        self.stop()

    def stop(self) -> None:
        """Stops the subscription."""
        self._has_been_stopped = True

    def __iter__(self) -> Self:
        return self

    @abstractmethod
    def __next__(self) -> Notification:
        """Returns the next Notification object in the application sequence."""


class ListenNotifySubscription(Subscription[TApplicationRecorder_co]):
    def __init__(
        self,
        recorder: TApplicationRecorder_co,
        gt: int | None = None,
        topics: Sequence[str] = (),
    ) -> None:
        super().__init__(recorder=recorder, gt=gt, topics=topics)
        self._select_limit = 500
        self._notifications: Sequence[Notification] = []
        self._notifications_index: int = 0
        self._notifications_queue: Queue[Sequence[Notification]] = Queue(maxsize=10)
        self._has_been_notified = Event()
        self._thread_error: BaseException | None = None
        self._pull_thread = Thread(target=self._loop_on_pull)
        self._pull_thread.start()

    def __exit__(self, *args: object, **kwargs: Any) -> None:
        try:
            super().__exit__(*args, **kwargs)
        finally:
            self._pull_thread.join()

    def stop(self) -> None:
        """Stops the subscription."""
        super().stop()
        self._notifications_queue.shutdown(  # pyright: ignore[reportAttributeAccessIssue]
            immediate=True
        )
        self._has_been_notified.set()

    def __next__(self) -> Notification:
        # If necessary, get a new list of notifications from the recorder.
        if (
            self._notifications_index == len(self._notifications)
            and not self._has_been_stopped
        ):
            try:
                self._notifications = self._notifications_queue.get()
            except ShutDown:
                pass
            else:
                self._notifications_queue.task_done()
                self._notifications_index = 0

        # Stop the iteration if subscription has been stopped.
        if self._has_been_stopped:
            # Maybe raise thread error.
            if self._thread_error is not None:
                raise self._thread_error
            raise StopIteration

        # Return a notification from previously obtained list.
        notification = self._notifications[self._notifications_index]
        self._notifications_index += 1
        return notification

    def _loop_on_pull(self) -> None:
        try:
            self._pull()  # Already recorded events.
            while not self._has_been_stopped:
                self._has_been_notified.wait()
                self._pull()  # Newly recorded events.
        except BaseException as e:
            if self._thread_error is None:
                self._thread_error = e
            self.stop()

    def _pull(self) -> None:
        while not self._has_been_stopped:
            self._has_been_notified.clear()
            notifications = self._recorder.select_notifications(
                start=self._last_notification_id or 0,
                limit=self._select_limit,
                topics=self._topics,
                inclusive_of_start=False,
            )
            if len(notifications) > 0:
                try:
                    self._notifications_queue.put(notifications)
                except ShutDown:
                    break
                self._last_notification_id = notifications[-1].id
            if len(notifications) < self._select_limit:
                break


class AggregateEventMapper(Mapper[TDecision]):
    def to_stored_event(self, domain_event: AggregateEvent[TDecision]) -> StoredEvent:
        topic = get_topic(type(domain_event.decision))
        stored_state = self.transcoder.encode(domain_event.decision)
        if self.compressor:
            stored_state = self.compressor.compress(stored_state)
        if self.cipher:
            stored_state = self.cipher.encrypt(stored_state)
        return StoredEvent(
            originator_id=domain_event.originator_id,
            originator_version=domain_event.originator_version,
            topic=topic,
            state=stored_state,
            uuid=domain_event.uuid,
            metadata=domain_event.metadata,
        )

    def to_domain_event(self, stored_event: StoredEvent) -> AggregateEvent[TDecision]:
        stored_state = stored_event.state
        try:
            if self.cipher:
                stored_state = self.cipher.decrypt(stored_state)
            if self.compressor:
                stored_state = self.compressor.decompress(stored_state)
            cls = resolve_topic(stored_event.topic)
            decision = self.transcoder.decode(stored_state, cls)
        except Exception as e:
            msg = (
                f"Failed to deserialise state of stored event with "
                f"topic '{stored_event.topic}', "
                f"originator_id '{stored_event.originator_id}' and "
                f"originator_version {stored_event.originator_version}: {e}"
            )
            raise MapperDeserialisationError(msg) from e
        else:
            return AggregateEvent[TDecision](
                decision=decision,
                uuid=stored_event.uuid,
                metadata=stored_event.metadata,
                originator_id=stored_event.originator_id,
                originator_version=stored_event.originator_version,
            )


class TaggedEventMapper(Generic[TDecision]):
    def __init__(
        self,
        transcoder: Transcoder[TDecision],
        compressor: Compressor | None = None,
        cipher: Cipher | None = None,
    ):
        self.transcoder = transcoder
        self.compressor = compressor
        self.cipher = cipher

    def to_dcb_event(self, event: TaggedEvent[TDecision]) -> DCBEvent:
        data = self.transcoder.encode(event.decision)
        if self.compressor:
            data = self.compressor.compress(data)
        if self.cipher:
            data = self.cipher.encrypt(data)
        return DCBEvent(
            type=get_topic(type(event.decision)),
            data=data,
            tags=event.tags,
            uuid=event.uuid,
            metadata=event.metadata,
        )

    def to_domain_event(self, event: DCBEvent) -> TaggedEvent[TDecision]:
        data = event.data
        if self.cipher:
            data = self.cipher.decrypt(data)
        if self.compressor:
            data = self.compressor.decompress(data)
        return TaggedEvent(
            tags=event.tags,
            decision=self.transcoder.decode(data, resolve_topic(event.type)),
            uuid=event.uuid,
            metadata=event.metadata,
        )
