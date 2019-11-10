from abc import ABC, ABCMeta, abstractmethod
from typing import TypeVar, Optional, Generic
from uuid import UUID


class MetaAbstractDomainEntity(ABCMeta):
    pass


class AbstractDomainEntity(ABC, metaclass=MetaAbstractDomainEntity):
    pass


class AbstractDomainEvent(ABC):
    pass


M = TypeVar('M', bound=MetaAbstractDomainEntity)
N = TypeVar('N', bound=AbstractDomainEntity)
V = TypeVar('V', bound=AbstractDomainEvent)


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
