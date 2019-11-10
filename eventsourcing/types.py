from abc import ABC, ABCMeta, abstractmethod
from typing import List, Optional, Union
from uuid import UUID


class MetaAbstractDomainEntity(ABCMeta):
    pass


class AbstractDomainEntity(ABC, metaclass=MetaAbstractDomainEntity):
    @abstractmethod
    def __publish__(
        self, event: Union["AbstractDomainEvent", List["AbstractDomainEvent"]]
    ):
        pass


class AbstractDomainEvent(ABC):
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def __mutate__(
        self, obj: Optional[AbstractDomainEntity] = None
    ) -> Optional[AbstractDomainEntity]:
        pass


class AbstractEventStore(ABC):
    """
    Abstract base class for event stores. Defines the methods
    expected of an event store by other classes in the library.
    """

    @abstractmethod
    def store(self, domain_event_or_events):
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
    ):
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


class AbstractEventPlayer(object):
    @property
    @abstractmethod
    def event_store(self) -> AbstractEventStore:
        """
        Returns event store object used by this repository.
        """


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


class AbstractEntityRepository(AbstractEventPlayer):
    @abstractmethod
    def __getitem__(self, entity_id) -> AbstractDomainEntity:
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
    def get_entity(self, entity_id, at=None) -> Optional[AbstractDomainEntity]:
        """
        Returns entity for given ID.

        Returns None when entity ID not found.
        """

    @abstractmethod
    def take_snapshot(
        self, entity_id: UUID, lt: int = None, lte: int = None
    ) -> Optional[AbstractSnapshop]:
        """
        Takes snapshot of entity state, using stored events.
        """


class AbstractRecordManager(ABC):
    @abstractmethod
    def record_sequenced_items(self, sequenced_item_or_items):
        """
        Writes sequenced item(s) into the datastore.
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


class AbstractSequencedItemMapper(ABC):
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
