from abc import ABC, ABCMeta, abstractmethod

from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)
from uuid import UUID

T = TypeVar("T")


class Event(object):
    """
    "I shall use the term 'event' in the more general sense
    of a nexus of actual occasions, inter-related in some
    determinate fashion in one extensive quantum. An actual
    occasion is the limiting type of an event with only one
    member."

    -- Alfred North Whitehead, 1929
    """


T_eo = TypeVar("T_eo", bound="EnduringObject")


class ActualOccasion(Event):
    """
    "'Actual entities' - also termed 'actual occasions' — are the final real things
    of which the world is made up. There is no going behind actual entities
    to find anything more real."

    "Just as 'potentiality for process' is the meaning of the more general term
    'entity' or 'thing; so 'decision' is the additional meaning imported by the
    word 'actual' into the phrase 'actual entity', 'Actuality' is the decision
    amid 'potentiality'. It represents stubborn fact which cannot be evaded."

    "Actual entities perish, but do not change; they are what they are."

    -- Alfred North Whitehead, 1929
    """

    pass


T_ao = TypeVar("T_ao", bound=ActualOccasion)


class AbstractDomainEvent(ActualOccasion, Generic[T_eo]):
    pass


T_evs = Sequence[T_ao]
T_ev_evs = Union[T_ao, T_evs]


# Todo: Delete this try/except when dropping support for Python 3.6.
# Need to deal with the fact that Python3.6 had GenericMeta.
try:
    from typing import GenericMeta

    ABCMeta = GenericMeta  # type: ignore

except ImportError:
    pass


class MetaAbstractDomainEntity(ABCMeta):
    pass


class EnduringObject(Event, metaclass=MetaAbstractDomainEntity):
    """
    "The notions of 'social order' and of 'personal order' cannot be omitted
    from this preliminary sketch. A 'society' in the sense in which that term
    is here used, is a nexus with social order; and an 'enduring object' or
    'enduring creature' is a society whose social order has taken the special
    form of 'personal order.'"

    "A nexus enjoys 'personal order' when (a) it is a 'society' and when
    the genetic relatedness of its members orders these members 'serially'."

    -- Alfred North Whitehead, 1929
    """


class AbstractEventStore(ABC, Generic[T_ao]):
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
    ) -> Iterable[T_ao]:
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
    ) -> Iterable[T_ao]:
        """
        Returns domain events for given entity ID.
        """

    @abstractmethod
    def get_domain_event(self, originator_id: UUID, position: int) -> T_ao:
        """
        Returns a single domain event.
        """

    @abstractmethod
    def get_most_recent_event(
        self, originator_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[T_ao]:
        """
        Returns most recent domain event for given entity ID.
        """

    @abstractmethod
    def all_domain_events(self) -> Iterable[T_ao]:
        """
        Returns all domain events in the event store.
        """


class AbstractEventPlayer(Generic[T_eo, T_ao]):
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
        initial_state: Optional[T_eo] = None,
        query_descending: bool = False,
    ) -> Optional[T_eo]:
        pass


class AbstractSnapshop(ActualOccasion):
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


class AbstractEntityRepository(AbstractEventPlayer[T_eo, T_ao]):
    @abstractmethod
    def __getitem__(self, entity_id: UUID) -> T_eo:
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
    def get_entity(self, entity_id: UUID, at: Optional[int] = None) -> Optional[T_eo]:
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


class AbstractRecordManager(ABC, Generic[T_ao]):
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


T_rm = TypeVar("T_rm", bound=AbstractRecordManager)


class AbstractSequencedItemMapper(Generic[T_ao], ABC):
    @abstractmethod
    def item_from_event(self, domain_event: T_ao) -> Tuple:
        """
        Constructs and returns a sequenced item for given domain event.
        """

    @abstractmethod
    def event_from_item(self, sequenced_item: Tuple) -> T_ao:
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
    def event_from_topic_and_state(self, topic: str, state: str) -> T_ao:
        """
        Resolves topic to an event class, decodes state, and constructs an event.
        """
