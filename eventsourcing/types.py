from abc import ABC, ABCMeta, abstractmethod
from decimal import Decimal
from typing import Generic, List, Optional, Sequence, Type, TypeVar, Union
from uuid import UUID


class MetaAbstractDomainEntity(ABCMeta):
    pass


# Need to deal with the fact that Python3.6 had GenericMeta.
try:
    from typing import GenericMeta

    class MetaAbstractDomainEntity(GenericMeta):  # type: ignore
        pass


except ImportError:
    pass
# Todo: Delete above try/except when dropping support for Python 3.6.

T = TypeVar("T")

T_id = TypeVar("T_id")

T_en = TypeVar("T_en", bound="AbstractDomainEntity")

T_ev = TypeVar("T_ev", bound="AbstractDomainEvent")

T_evs = Sequence[T_ev]

T_ev_evs = Union[T_ev, T_evs]


class AbstractDomainEntity(Generic[T_ev], metaclass=MetaAbstractDomainEntity):
    @property
    @abstractmethod
    def id(self) -> UUID:
        pass

    @classmethod
    @abstractmethod
    def __create__(
        cls: Type[T_en],
        originator_id: Optional[UUID] = None,
        event_class: Optional[Type[T_ev]] = None,
        **kwargs
    ) -> T_en:
        """
        Constructs, applies, and publishes a domain event.
        """

    @abstractmethod
    def __trigger_event__(self, event_class: Type[T_ev], **kwargs) -> None:
        """
        Constructs, applies, and publishes a domain event.
        """

    @abstractmethod
    def __mutate__(self, event: T_ev) -> None:
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


class AbstractDomainEvent(Generic[T_en]):
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def __mutate__(self, obj: Optional[T_en]) -> Optional[T_en]:
        pass

    @abstractmethod
    def mutate(self: T_ev, obj: T_en) -> None:
        pass


class AbstractEventWithTimestamp(AbstractDomainEvent[T_en]):

    @property
    @abstractmethod
    def timestamp(self) -> Decimal:
        pass


class AbstractEventWithOriginatorID(AbstractDomainEvent[T_en], Generic[T_en, T_id]):

    @property
    @abstractmethod
    def originator_id(self) -> T_id:
        pass


class AbstractEventWithOriginatorVersion(AbstractDomainEvent[T_en]):

    @property
    @abstractmethod
    def originator_version(self) -> int:
        pass


class AbstractEventStore(ABC):
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
        originator_id,
        gt=None,
        gte=None,
        lt=None,
        lte=None,
        limit=None,
        is_ascending=True,
        page_size=None,
    ) -> T_evs:
        """
        Returns domain events for given entity ID.
        """

    @abstractmethod
    def get_domain_event(self, originator_id, position):
        """
        Returns a single domain event.
        """

    @abstractmethod
    def get_most_recent_event(self, originator_id, lt=None, lte=None):
        """
        Returns most recent domain event for given entity ID.
        """

    @abstractmethod
    def all_domain_events(self):
        """
        Returns all domain events in the event store.
        """


class AbstractEventPlayer(Generic[T_en]):
    @property
    @abstractmethod
    def event_store(self) -> AbstractEventStore:
        """
        Returns event store object used by this repository.
        """

    @abstractmethod
    def get_and_project_events(
        self,
        entity_id,
        gt=None,
        gte=None,
        lt=None,
        lte=None,
        limit=None,
        initial_state=None,
        query_descending=False,
    ):
        pass


class AbstractSnapshop(ABC):
    @property
    @abstractmethod
    def topic(self):
        """
        Path to the class of the snapshotted entity.
        """

    @property
    @abstractmethod
    def state(self):
        """
        State of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_id(self):
        """
        ID of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_version(self):
        """
        Version of the last event applied to the entity.
        """


class AbstractEntityRepository(AbstractEventPlayer[T_en]):
    @abstractmethod
    def __getitem__(self, entity_id) -> T_en:
        """
        Returns entity for given ID.

        Raises ``RepositoryKeyError`` when entity ID not found.
        """

    @abstractmethod
    def __contains__(self, entity_id) -> bool:
        """
        Returns True or False, according to whether or not entity exists.
        """

    @abstractmethod
    def get_entity(self, entity_id, at: Optional[int]=None) -> Optional[T_en]:
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


class AbstractRecordManager(ABC):
    @abstractmethod
    def record_sequenced_items(self, sequenced_item_or_items: List):
        """
        Writes sequenced item(s) into the datastore.
        """

    @abstractmethod
    def get_items(self, sequence_id, position):
        """
        Gets record at position in sequence.
        """

    @abstractmethod
    def get_record(self, sequence_id, position):
        """
        Gets record at position in sequence.
        """

    @abstractmethod
    def get_records(
        self,
        sequence_id,
        gt=None,
        gte=None,
        lt=None,
        lte=None,
        limit=None,
        query_ascending=True,
        results_ascending=True,
    ):
        """
        Returns records for a sequence.
        """

    @abstractmethod
    def get_notifications(self, start=None, stop=None, *args, **kwargs):
        """
        Returns records sequenced by notification ID, from
        application, for pipeline, in given range.

        Args 'start' and 'stop' are positions in a zero-based
        integer sequence.
        """

    @abstractmethod
    def all_sequence_ids(self):
        """
        Returns all sequence IDs.
        """

    @abstractmethod
    def delete_record(self, record):
        """
        Removes permanently given record from the table.
        """


T_rm = TypeVar('T_rm', bound=AbstractRecordManager)


class AbstractSequencedItemMapper(Generic[T_ev], ABC):
    @abstractmethod
    def item_from_event(self, domain_event):
        """
        Constructs and returns a sequenced item for given domain event.
        """

    @abstractmethod
    def event_from_item(self, sequenced_item):
        """
        Constructs and returns a domain event for given sequenced item.
        """

    @abstractmethod
    def json_dumps(self, event_attrs):
        """
        Encodes given object as JSON.
        """

    @abstractmethod
    def json_loads(self, event_attrs):
        """
        Decodes given JSON as object.
        """

    @abstractmethod
    def event_from_topic_and_state(self, topic, state) -> T_ev:
        """
        Resolves topic to an event class, decodes state, and constructs an event.
        """
