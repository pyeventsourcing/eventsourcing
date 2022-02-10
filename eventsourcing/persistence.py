import json
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from threading import Condition, Event, Lock, Semaphore, Timer
from time import time
from types import ModuleType
from typing import (
    Any,
    Deque,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

from eventsourcing.domain import DomainEvent, EventSourcingError
from eventsourcing.utils import (
    Environment,
    TopicError,
    get_topic,
    resolve_topic,
    strtobool,
)


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
        self.encoder = json.JSONEncoder(default=self._encode_obj, separators=(",", ":"))
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
                "serializable. Please define and register "
                "a custom transcoding for this type."
            ) from None
        else:
            return {
                "_type_": transcoding.name,
                "_data_": transcoding.encode(o),
            }

    def _decode_obj(self, d: Dict[str, Any]) -> Any:
        if len(d) == 2:
            try:
                _type_ = d["_type_"]
            except KeyError:
                return d
            else:
                try:
                    _data_ = d["_data_"]
                except KeyError:
                    return d
                else:
                    try:
                        transcoding = self.names[cast(str, _type_)]
                    except KeyError:
                        raise TypeError(
                            f"Data serialized with name '{cast(str, _type_)}' is not "
                            "deserializable. Please register a "
                            "custom transcoding for this type."
                        )
                    else:
                        return transcoding.decode(_data_)
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
    """
    Frozen dataclass that represents :class:`~eventsourcing.domain.DomainEvent`
    objects, such as aggregate :class:`~eventsourcing.domain.Aggregate.Event`
    objects and :class:`~eventsourcing.domain.Snapshot` objects.

    Constructor parameters:

    :param UUID originator_id: ID of the originating aggregate
    :param int originator_version: version of the originating aggregate
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
    def __init__(self, environment: Environment):
        """
        Initialises cipher with given environment.
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


class Mapper:
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

    def from_domain_event(self, domain_event: DomainEvent[Any]) -> StoredEvent:
        """
        Converts the given domain event to a :class:`StoredEvent` object.
        """
        topic: str = get_topic(domain_event.__class__)
        event_state = domain_event.__dict__.copy()
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

    def to_domain_event(self, stored: StoredEvent) -> DomainEvent[Any]:
        """
        Converts the given :class:`StoredEvent` to a domain event object.
        """
        stored_state: bytes = stored.state
        if self.cipher:
            stored_state = self.cipher.decrypt(stored_state)
        if self.compressor:
            stored_state = self.compressor.decompress(stored_state)
        event_state: Dict[str, Any] = self.transcoder.decode(stored_state)
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


class RecordConflictError(EventSourcingError):
    """
    Legacy exception, replaced with IntegrityError.
    """


class PersistenceError(EventSourcingError):
    """
    The base class of the other exceptions in this module.

    Exception class names follow https://www.python.org/dev/peps/pep-0249/#exceptions
    """


class InterfaceError(PersistenceError):
    """
    Exception raised for errors that are related to the database
    interface rather than the database itself.
    """


class DatabaseError(PersistenceError):
    """
    Exception raised for errors that are related to the database.
    """


class DataError(DatabaseError):
    """
    Exception raised for errors that are due to problems with the
    processed data like division by zero, numeric value out of range, etc.
    """


class OperationalError(DatabaseError):
    """
    Exception raised for errors that are related to the database’s
    operation and not necessarily under the control of the programmer,
    e.g. an unexpected disconnect occurs, the data source name is not
    found, a transaction could not be processed, a memory allocation
    error occurred during processing, etc.
    """


class IntegrityError(DatabaseError, RecordConflictError):
    """
    Exception raised when the relational integrity of the
    database is affected, e.g. a foreign key check fails.
    """


class InternalError(DatabaseError):
    """
    Exception raised when the database encounters an internal
    error, e.g. the cursor is not valid anymore, the transaction
    is out of sync, etc.
    """


class ProgrammingError(DatabaseError):
    """
    Exception raised for database programming errors, e.g. table
    not found or already exists, syntax error in the SQL statement,
    wrong number of parameters specified, etc.
    """


class NotSupportedError(DatabaseError):
    """
    Exception raised in case a method or database API was used
    which is not supported by the database, e.g. calling the
    rollback() method on a connection that does not support
    transaction or has transactions turned off.
    """


class AggregateRecorder(ABC):
    """
    Abstract base class for recorders that record and
    retrieve stored events for domain model aggregates.
    """

    @abstractmethod
    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
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


# Todo: Reimplement select_events() methods, to get in batches in case lots of events.


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
    def select_notifications(
        self,
        start: int,
        limit: int,
        stop: Optional[int] = None,
        topics: Sequence[str] = (),
    ) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit' and
        optionally by 'stop'.
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


@dataclass(frozen=True)
class Recording:
    domain_event: DomainEvent[Any]
    notification: Notification


class EventStore:
    """
    Stores and retrieves domain events.
    """

    def __init__(
        self,
        mapper: Mapper,
        recorder: AggregateRecorder,
    ):
        self.mapper = mapper
        self.recorder = recorder

    def put(
        self, domain_events: Sequence[DomainEvent[Any]], **kwargs: Any
    ) -> List[Recording]:
        """
        Stores domain events in aggregate sequence.
        """
        stored_events = list(map(self.mapper.from_domain_event, domain_events))
        recordings = []
        notification_ids = self.recorder.insert_events(stored_events, **kwargs)
        if notification_ids:
            assert len(notification_ids) == len(stored_events)
            for d, s, n_id in zip(domain_events, stored_events, notification_ids):
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
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> Iterator[DomainEvent[Any]]:
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


TF = TypeVar("TF", bound="InfrastructureFactory")


class InfrastructureFactory(ABC):
    """
    Abstract base class for infrastructure factories.
    """

    PERSISTENCE_MODULE = "PERSISTENCE_MODULE"
    MAPPER_TOPIC = "MAPPER_TOPIC"
    CIPHER_TOPIC = "CIPHER_TOPIC"
    COMPRESSOR_TOPIC = "COMPRESSOR_TOPIC"
    IS_SNAPSHOTTING_ENABLED = "IS_SNAPSHOTTING_ENABLED"

    @classmethod
    def construct(cls: Type[TF], env: Environment) -> TF:
        """
        Constructs concrete infrastructure factory for given
        named application. Reads and resolves persistence
        topic from environment variable 'PERSISTENCE_MODULE'.
        """
        factory_cls: Type[TF]
        # noinspection SpellCheckingInspection
        topic = (
            env.get(
                "INFRASTRUCTURE_FACTORY",  # Legacy.
                "",
            )
            or env.get(
                "FACTORY_TOPIC",  # Legacy.
                "",
            )
            or env.get(
                cls.PERSISTENCE_MODULE,
                "eventsourcing.popo:Factory",
            )
        )
        try:
            obj: Union[Type[TF], ModuleType] = resolve_topic(topic)
        except TopicError as e:
            raise EnvironmentError(
                "Failed to resolve persistence module topic: "
                f"'{topic}' from environment "
                f"variable '{cls.PERSISTENCE_MODULE}'"
            ) from e

        if isinstance(obj, ModuleType):
            # Find the factory in the module.
            factory_classes: List[Type[TF]] = []
            for member in obj.__dict__.values():
                if (
                    isinstance(member, type)
                    and issubclass(member, InfrastructureFactory)
                    and member != InfrastructureFactory
                ):
                    factory_classes.append(cast(Type[TF], member))
            if len(factory_classes) == 1:
                factory_cls = factory_classes[0]
            else:
                raise AssertionError(
                    f"Found {len(factory_classes)} infrastructure factory classes in"
                    f" '{topic}', expected 1."
                )
        elif isinstance(obj, type) and issubclass(obj, InfrastructureFactory):
            factory_cls = obj
        else:
            raise AssertionError(
                f"Not an infrastructure factory class or module: {topic}"
            )
        return factory_cls(env=env)

    def __init__(self, env: Environment):
        """
        Initialises infrastructure factory object with given application name.
        """
        self.env = env

    def transcoder(
        self,
    ) -> Transcoder:
        """
        Constructs a transcoder.
        """
        return JSONTranscoder()

    def mapper(
        self,
        transcoder: Transcoder,
    ) -> Mapper:
        """
        Constructs a mapper.
        """
        return Mapper(
            transcoder=transcoder,
            cipher=self.cipher(),
            compressor=self.compressor(),
        )

    def cipher(self) -> Optional[Cipher]:
        """
        Reads environment variables 'CIPHER_TOPIC'
        and 'CIPHER_KEY' to decide whether or not
        to construct a cipher.
        """
        cipher_topic = self.env.get(self.CIPHER_TOPIC)
        cipher: Optional[Cipher] = None
        default_cipher_topic = "eventsourcing.cipher:AESCipher"
        if self.env.get("CIPHER_KEY") and not cipher_topic:
            cipher_topic = default_cipher_topic

        if cipher_topic:
            cipher_cls: Type[Cipher] = resolve_topic(cipher_topic)
            cipher = cipher_cls(self.env)

        return cipher

    def compressor(self) -> Optional[Compressor]:
        """
        Reads environment variable 'COMPRESSOR_TOPIC' to
        decide whether or not to construct a compressor.
        """
        compressor: Optional[Compressor] = None
        compressor_topic = self.env.get(self.COMPRESSOR_TOPIC)
        if compressor_topic:
            compressor_cls: Union[Type[Compressor], Compressor] = resolve_topic(
                compressor_topic
            )
            if isinstance(compressor_cls, type):
                compressor = compressor_cls()
            else:
                compressor = compressor_cls
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
        return strtobool(self.env.get(self.IS_SNAPSHOTTING_ENABLED, "no"))

    def close(self) -> None:
        """
        Closes any database connections, or anything else that needs closing.
        """


@dataclass(frozen=True)
class Tracking:
    """
    Frozen dataclass representing the position of a domain
    event :class:`Notification` in an application's notification log.
    """

    application_name: str
    notification_id: int


class Cursor(ABC):
    @abstractmethod
    def execute(self, statement: Union[str, bytes], params: Any = None) -> None:
        """Executes given statement."""

    @abstractmethod
    def fetchall(self) -> Any:
        """Fetches all results."""

    @abstractmethod
    def fetchone(self) -> Any:
        """Fetches one result."""


TCursor = TypeVar("TCursor", bound=Cursor)


class Connection(ABC, Generic[TCursor]):
    def __init__(self, max_age: Optional[float] = None) -> None:
        self._closed = False
        self._closing = Event()
        self._close_lock = Lock()
        self.in_use = Lock()
        self.in_use.acquire()
        if max_age is not None:
            self._max_age_timer: Optional[Timer] = Timer(
                interval=max_age,
                function=self._close_when_not_in_use,
            )
            self._max_age_timer.daemon = True
            self._max_age_timer.start()
        else:
            self._max_age_timer = None
        self.is_writer: Optional[bool] = None

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


class ConnectionPoolClosed(EventSourcingError):
    pass


class ConnectionNotFromPool(EventSourcingError):
    pass


class WriterBlockedByReaders(OperationalError):
    pass


class ReaderBlockedByWriter(OperationalError):
    pass


class WriterBlockedByWriter(OperationalError):
    pass


class ConnectionPoolExhausted(OperationalError):
    pass


class ConnectionPool(ABC, Generic[TConnection]):
    def __init__(
        self,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: float = 30.0,
        max_age: Optional[float] = None,
        pre_ping: bool = False,
        mutually_exclusive_read_write: bool = False,
    ) -> None:
        """
        Initialises a new connection pool.

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
        self._pool: Deque[TConnection] = deque()
        self._in_use: Dict[int, TConnection] = dict()
        self._get_semaphore = Semaphore()
        self._put_condition = Condition()
        self._no_readers = Condition()
        self._num_readers: int = 0
        self._writer_lock = Lock()
        self._mutually_exclusive_read_write = mutually_exclusive_read_write
        self._closed = False

    @property
    def num_in_use(self) -> int:
        """
        Indicates the total number of connections currently in use.
        """
        with self._put_condition:
            return self._num_in_use

    @property
    def _num_in_use(self) -> int:
        return len(self._in_use)

    @property
    def num_in_pool(self) -> int:
        """
        Indicates the number of connections currently in the pool.
        """
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
        self, timeout: Optional[float] = None, is_writer: Optional[bool] = None
    ) -> TConnection:
        """
        Issues connections, or raises ConnectionPoolExhausted error.
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
            raise ConnectionPoolClosed

        # Decide the timeout for getting a connection.
        timeout = self.pool_timeout if timeout is None else timeout

        # Remember when we started trying to get a connection.
        started = time()

        # Join queue of threads waiting to get a connection ("fairness").
        with self._get_semaphore:
            # If connection is for writing, get write lock and wait for no readers.
            if is_writer is True:
                remaining = self._remaining_timeout(timeout, started)
                if not self._writer_lock.acquire(timeout=remaining):
                    raise WriterBlockedByWriter()
                if self._mutually_exclusive_read_write:
                    with self._no_readers:
                        if self._num_readers > 0:
                            remaining = self._remaining_timeout(timeout, started)
                            # print("writer waiting")
                            if not self._no_readers.wait(timeout=remaining):
                                self._writer_lock.release()
                                raise WriterBlockedByReaders()

            # If connection is for reading and writing excludes reading,
            # then wait for the write lock, and increment number of readers.
            elif is_writer is False:
                if self._mutually_exclusive_read_write:
                    remaining = self._remaining_timeout(timeout, started)
                    if not self._writer_lock.acquire(timeout=remaining):
                        raise ReaderBlockedByWriter()
                    self._writer_lock.release()
                    with self._no_readers:
                        self._num_readers += 1

            # Actually try to get a connection withing the time remaining.
            conn = self._get_connection(
                timeout=self._remaining_timeout(timeout, started)
            )

            # Remember if this connection is for reading or writing.
            conn.is_writer = is_writer

            # Return the connection.
            return conn

    def _get_connection(self, timeout: float = 0.0) -> TConnection:
        """
        Gets or creates connections from pool within given
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
                        timeout=self._remaining_timeout(timeout, started)
                    ):
                        # Connection has been returned, so try again.
                        return self._get_connection(
                            timeout=self._remaining_timeout(timeout, started)
                        )
                    else:
                        # Timed out waiting for a connection to be returned.
                        raise ConnectionPoolExhausted("Pool is exhausted") from None
                else:
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
                        timeout=self._remaining_timeout(timeout, started)
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
                            timeout=self._remaining_timeout(timeout, started)
                        )

            # Track the connection is now being used.
            self._in_use[id(conn)] = conn

            # Return the connection.
            return conn

    def put_connection(self, conn: TConnection) -> None:
        """
        Returns connections to the pool, or closes connection
        if the pool is full.

        Unlocks write lock after writer has returned., and
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
                raise ConnectionPoolClosed("Pool is closed")

            # Make sure we are dealing with a connection from this pool.
            try:
                del self._in_use[id(conn)]
            except KeyError:
                raise ConnectionNotFromPool(
                    "Connection not in use in this pool"
                ) from None

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
                self._writer_lock.release()

            # Or if it was for reading, decrement the number of readers.
            elif is_writer is False and self._mutually_exclusive_read_write:
                with self._no_readers:
                    self._num_readers -= 1
                    if self._num_readers == 0:
                        self._no_readers.notify()

            # Notify a thread that is waiting for a connection to be returned.
            self._put_condition.notify()

    @abstractmethod
    def _create_connection(self) -> TConnection:
        """
        Create a new connection.

        Subclasses should implement this method by
        creating a database connection of the type
        being pooled.
        """

    def close(self) -> None:
        """
        Close the connection pool.
        """
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
    def _remaining_timeout(timeout: float, started: float) -> float:
        return max(0.0, timeout + started - time())

    def __del__(self) -> None:
        self.close()
