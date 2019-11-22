from abc import ABC, ABCMeta, abstractmethod
from decimal import Decimal

from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID


# Todo: Delete this try/except when dropping support for Python 3.6.
# Need to deal with the fact that Python3.6 had GenericMeta.
try:
    from typing import GenericMeta

    ABCMeta = GenericMeta  # type: ignore

except ImportError:
    pass


class MetaAbstractDomainEntity(ABCMeta):
    pass


T = TypeVar("T")

T_aen = TypeVar("T_aen", bound="AbstractDomainEntity")

T_aev = TypeVar("T_aev", bound="AbstractDomainEvent")

T_evs = Sequence[T_aev]

T_ev_evs = Union[T_aev, T_evs]

T_rm = TypeVar("T_rm", bound="AbstractRecordManager")

T_es = TypeVar("T_es", bound="AbstractEventStore")


class AbstractDomainEntity(metaclass=MetaAbstractDomainEntity):
    @property
    @abstractmethod
    def id(self) -> UUID:
        pass

    @classmethod
    @abstractmethod
    def __create__(
        cls: Type[T_aen],
        originator_id: Optional[UUID] = None,
        event_class: Optional[Type[T_aev]] = None,
        **kwargs: Any
    ) -> T_aen:
        """
        Constructs, applies, and publishes a domain event.
        """

    @abstractmethod
    def __trigger_event__(self, event_class: Type[T_aev], **kwargs: Any) -> None:
        """
        Constructs, applies, and publishes a domain event.
        """

    @abstractmethod
    def __mutate__(self, event: T_aev) -> None:
        """
        Mutates this entity with the given event.
        """

    @abstractmethod
    def __publish__(self, event: T_ev_evs) -> None:
        """
        Publishes given event for subscribers in the application.
        """

    @abstractmethod
    def __assert_not_discarded__(self) -> None:
        """
        Asserts that this entity has not been discarded.
        """

    # @property
    # @classmethod
    # @abstractmethod
    # def Event(cls) -> Type[T_ev]:
    #     pass
    #
    # @property
    # @classmethod
    # @abstractmethod
    # def Created(cls) -> Type[T_ev]:
    #     pass

    # @property
    # @classmethod
    # @abstractmethod
    # def AttributeChanged(cls) -> Type[T_ev]:
    #     pass
    #
    # @property
    # @classmethod
    # @abstractmethod
    # def Discarded(self) -> Type[T_ev]:
    #     pass


class AbstractDomainEvent(ABC, Generic[T_aen]):
    @abstractmethod
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def __mutate__(self, obj: Optional[T_aen]) -> Optional[T_aen]:
        pass

    @abstractmethod
    def mutate(self, obj: T_aen) -> None:
        pass


class AbstractEventWithTimestamp(AbstractDomainEvent):
    @property
    @abstractmethod
    def timestamp(self) -> Decimal:
        pass


class AbstractEventWithOriginatorID(AbstractDomainEvent):
    @property
    @abstractmethod
    def originator_id(self) -> UUID:
        pass


class AbstractEventWithOriginatorVersion(AbstractDomainEvent):
    @property
    @abstractmethod
    def originator_version(self) -> int:
        pass


class AbstractEventStore(ABC, Generic[T_aev]):
    """
    Abstract base class for event stores. Defines the methods
    expected of an event store by other classes in the library.
    """

    @abstractmethod
    def store(self, domain_event_or_events: T_ev_evs) -> None:
        """
        Put domain event in event store for later retrieval.
        """

    @abstractmethod
    def get_domain_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        is_ascending: bool = True,
        page_size: Optional[int] = None,
    ) -> Iterable[T_aev]:
        """
        Deprecated. Please use iter_domain_events() instead.

        Returns domain events for given entity ID.
        """

    @abstractmethod
    def iter_domain_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        is_ascending: bool = True,
        page_size: Optional[int] = None,
    ) -> Iterable[T_aev]:
        """
        Returns domain events for given entity ID.
        """

    @abstractmethod
    def get_domain_event(self, originator_id: UUID, position: int) -> T_aev:
        """
        Returns a single domain event.
        """

    @abstractmethod
    def get_most_recent_event(
        self, originator_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[T_aev]:
        """
        Returns most recent domain event for given entity ID.
        """

    @abstractmethod
    def all_domain_events(self) -> Iterable[T_aev]:
        """
        Returns all domain events in the event store.
        """


class AbstractEventPlayer(Generic[T_aen, T_aev]):
    @property
    @abstractmethod
    def event_store(self) -> AbstractEventStore:
        """
        Returns event store object used by this repository.
        """

    @abstractmethod
    def get_and_project_events(
        self,
        entity_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        initial_state: Optional[T_aen] = None,
        query_descending: bool = False,
    ) -> Optional[T_aen]:
        pass


class AbstractSnapshop(AbstractDomainEvent):
    @property
    @abstractmethod
    def topic(self) -> str:
        """
        Path to the class of the snapshotted entity.
        """

    @property
    @abstractmethod
    def state(self) -> str:
        """
        State of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_id(self) -> UUID:
        """
        ID of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_version(self) -> int:
        """
        Version of the last event applied to the entity.
        """


class AbstractEntityRepository(AbstractEventPlayer[T_aen, T_aev]):
    @abstractmethod
    def __getitem__(self, entity_id: UUID) -> T_aen:
        """
        Returns entity for given ID.

        Raises ``RepositoryKeyError`` when entity ID not found.
        """

    @abstractmethod
    def __contains__(self, entity_id: UUID) -> bool:
        """
        Returns True or False, according to whether or not entity exists.
        """

    @abstractmethod
    def get_entity(self, entity_id: UUID, at: Optional[int] = None) -> Optional[T_aen]:
        """
        Returns entity for given ID.

        Returns None when entity ID not found.
        """

    @abstractmethod
    def take_snapshot(
        self, entity_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[AbstractSnapshop]:
        """
        Takes snapshot of entity state, using stored events.
        """


class AbstractRecordManager(ABC, Generic[T_aev]):
    @property
    @abstractmethod
    def record_class(self) -> Any:
        pass

    @abstractmethod
    def record_sequenced_items(
        self, sequenced_item_or_items: Union[Sequence[Tuple], Tuple]
    ) -> None:
        """
        Writes sequenced item(s) into the datastore.
        """

    @abstractmethod
    def get_item(self, sequence_id: UUID, position: int) -> Tuple:
        """
        Gets sequenced item from the datastore.
        """

    @abstractmethod
    def get_items(
        self,
        sequence_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        query_ascending: bool = True,
        results_ascending: bool = True,
    ) -> Iterator[T_evs]:
        """
        Iterates over records in sequence.
        """

    @abstractmethod
    def get_record(self, sequence_id: UUID, position: int) -> Any:
        """
        Gets record at position in sequence.
        """

    @abstractmethod
    def get_records(
        self,
        sequence_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        query_ascending: bool = True,
        results_ascending: bool = True,
    ) -> Sequence[Any]:
        """
        Returns records for a sequence.
        """

    @abstractmethod
    def get_notifications(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Returns records sequenced by notification ID, from
        application, for pipeline, in given range.

        Args 'start' and 'stop' are positions in a zero-based
        integer sequence.
        """

    @abstractmethod
    def all_sequence_ids(self) -> Sequence[UUID]:
        """
        Returns all sequence IDs.
        """

    @abstractmethod
    def delete_record(self, record: Any) -> None:
        """
        Removes permanently given record from the table.
        """


class AbstractSequencedItemMapper(Generic[T_aev], ABC):
    @abstractmethod
    def item_from_event(self, domain_event: T_aev) -> Tuple:
        """
        Constructs and returns a sequenced item for given domain event.
        """

    @abstractmethod
    def event_from_item(self, sequenced_item: Tuple) -> T_aev:
        """
        Constructs and returns a domain event for given sequenced item.
        """

    @abstractmethod
    def json_dumps(self, o: object) -> str:
        """
        Encodes given object as JSON.
        """

    @abstractmethod
    def json_loads(self, s: str) -> object:
        """
        Decodes given JSON as object.
        """

    @abstractmethod
    def event_from_topic_and_state(self, topic: str, state: str) -> T_aev:
        """
        Resolves topic to an event class, decodes state, and constructs an event.
        """
