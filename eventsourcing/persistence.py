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
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

from eventsourcing.domain import DomainEvent, TDomainEvent
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
                "serializable. Please define and register "
                "a custom transcoding for this type."
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


class RecordConflictError(Exception):
    """
    Legacy exception, replaced with IntegrityError.
    """


class PersistenceError(Exception):
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
    Exception raised for programming errors, e.g. table not
    found or already exists, syntax error in the SQL statement,
    wrong number of parameters specified, etc.
    """


class NotSupportedError(DatabaseError):
    """
    Exception raised in case a method or database API was used
    which is not supported by the database, e.g. calling the
    rollback() method on a connection that does not support
    transaction or has transactions turned off.
    """


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
    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Sequence[Tuple[StoredEvent, Optional[int]]]:
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
        self, start: int, limit: int, topics: Sequence[str] = ()
    ) -> List[Notification]:
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
        mapper: Mapper,
        recorder: AggregateRecorder,
    ):
        self.mapper = mapper
        self.recorder = recorder

    def put(
        self, events: Sequence[DomainEvent[Any]], **kwargs: Any
    ) -> Sequence[Tuple[StoredEvent, Optional[int]]]:
        """
        Stores domain events in aggregate sequence.
        """
        return self.recorder.insert_events(
            list(map(self.mapper.from_domain_event, events)), **kwargs
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
        return cast(
            Iterator[TDomainEvent],
            map(
                self.mapper.to_domain_event,
                self.recorder.select_events(
                    originator_id=originator_id,
                    gt=gt,
                    lte=lte,
                    desc=desc,
                    limit=limit,
                ),
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
    CIPHER_KEY = "CIPHER_KEY"
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
        except TopicError:
            raise EnvironmentError(
                "Failed to resolve "
                "infrastructure factory topic: "
                f"'{topic}' from environment "
                f"variable '{cls.PERSISTENCE_MODULE}'"
            )

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
        cipher_key = self.env.get(self.CIPHER_KEY)
        cipher: Optional[Cipher] = None
        if cipher_topic:
            if not cipher_key:
                raise EnvironmentError(
                    f"'{self.CIPHER_KEY}' not set in env, "
                    f"although '{self.CIPHER_TOPIC}' was set"
                )
        elif cipher_key:
            cipher_topic = "eventsourcing.cipher:AESCipher"

        if cipher_topic and cipher_key:
            cipher_cls: Type[Cipher] = resolve_topic(cipher_topic)
            cipher = cipher_cls(cipher_key=cipher_key)

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
    def event_store(**kwargs: Any) -> EventStore[TDomainEvent]:
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
                function=self._close_on_timer,
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

    def _close_on_timer(self) -> None:
        self._closing.set()
        with self.in_use:
            if not self._closed:
                self.close()


TConnection = TypeVar("TConnection", bound=Connection[Any])


class ConnectionPoolClosed(Exception):
    pass


class ConnectionNotFromPool(Exception):
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
        pool_size: int = 1,
        max_overflow: int = 0,
        pool_timeout: float = 5.0,
        max_age: Optional[float] = None,
        pre_ping: bool = False,
        mutually_exclusive_read_write: bool = True,
    ) -> None:
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
        with self._put_condition:
            return self._num_in_use

    @property
    def _num_in_use(self) -> int:
        return len(self._in_use)

    @property
    def num_in_pool(self) -> int:
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
        if self._closed:
            raise ConnectionPoolClosed
        timeout = self.pool_timeout if timeout is None else timeout
        started = time()

        # if is_writer is True:
        #     print("writer getting connection")

        with self._get_semaphore:
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
            elif is_writer is False:
                remaining = self._remaining_timeout(timeout, started)
                if self._mutually_exclusive_read_write:
                    if not self._writer_lock.acquire(timeout=remaining):
                        raise ReaderBlockedByWriter()
                    with self._no_readers:
                        self._num_readers += 1
                    self._writer_lock.release()

            conn = self._get_connection(
                timeout=self._remaining_timeout(timeout, started)
            )
            if is_writer is not None:
                conn.is_writer = is_writer

            # if is_writer is None:
            #     for_writer = ""
            # elif is_writer:
            #     for_writer = "for writer"
            # else:
            #     for_writer = "for reader"
            # print(
            #     "got connection",
            #     for_writer,
            #     self.num_in_pool,
            #     "pooled,",
            #     self.num_in_use,
            #     "used",
            # )

            return conn

    def _get_connection(self, timeout: float = 0.0) -> TConnection:
        started = time()
        with self._put_condition:
            try:
                conn = self._pool.popleft()
            except IndexError:
                # print("pool empty")
                if not self._is_use_full:
                    # print("created another connection")
                    conn = self._create_connection()
                    self._in_use[id(conn)] = conn
                    return conn
                else:
                    if self._put_condition.wait(
                        timeout=self._remaining_timeout(timeout, started)
                    ):
                        return self._get_connection(
                            timeout=self._remaining_timeout(timeout, started)
                        )
                    else:
                        raise ConnectionPoolExhausted("Pool is exhausted") from None

            else:
                if conn.closing or not conn.in_use.acquire(blocking=False):
                    return self._get_connection(
                        timeout=self._remaining_timeout(timeout, started)
                    )
                elif conn.closed:
                    return self._get_connection(
                        timeout=self._remaining_timeout(timeout, started)
                    )
                elif self.pre_ping:
                    try:
                        conn.cursor().execute("SELECT 1")
                    except Exception:
                        return self._get_connection(
                            timeout=self._remaining_timeout(timeout, started)
                        )
                self._in_use[id(conn)] = conn
                return conn

    @staticmethod
    def _remaining_timeout(timeout: float, started: float) -> float:
        return max(0.0, timeout + started - time())

    def put_connection(self, conn: TConnection) -> None:
        # print("putting connection", self.num_in_pool, "in pool")

        is_writer = conn.is_writer
        conn.is_writer = None
        with self._put_condition:
            if self._closed:
                raise ConnectionPoolClosed("Pool is closed")

            try:
                del self._in_use[id(conn)]
            except KeyError:
                raise ConnectionNotFromPool(
                    "Connection not in use in this pool"
                ) from None
            try:
                if not conn.closed:
                    if conn.closing or self._is_pool_full:
                        # print(
                        #     "closing connection",
                        #     f"pool {'is' if self._is_pool_full else 'not'} full",
                        # )
                        conn.close()
                    else:
                        self._pool.append(conn)
            finally:
                conn.in_use.release()

                if is_writer is True:
                    self._writer_lock.release()
                elif is_writer is False and self._mutually_exclusive_read_write:
                    with self._no_readers:
                        self._num_readers -= 1
                        if self._num_readers == 0:
                            self._no_readers.notify()
                self._put_condition.notify()
            # if is_writer is None:
            #     for_writer = ""
            # elif is_writer:
            #     for_writer = "for writer"
            # else:
            #     for_writer = "for reader"
            # print(
            #     "put connection",
            #     for_writer,
            #     self.num_in_pool,
            #     "pooled,",
            #     self.num_in_use,
            #     "used",
            # )

    @abstractmethod
    def _create_connection(self) -> TConnection:
        """Creates new connection."""

    def close(self) -> None:
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

    def __del__(self) -> None:
        self.close()
