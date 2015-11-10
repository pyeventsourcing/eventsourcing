from abc import abstractmethod, ABCMeta
from six import with_metaclass
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber


class EventSourcingApplication(with_metaclass(ABCMeta)):

    def __init__(self):
        self.stored_event_repo = self.create_stored_event_repo()
        self.event_store = self.create_event_store()
        self.persistence_subscriber = self.create_persistence_subscriber()

    @abstractmethod
    def create_stored_event_repo(self):
        raise NotImplementedError()

    def create_event_store(self):
        return EventStore(stored_event_repo=self.stored_event_repo)

    def create_persistence_subscriber(self):
        return PersistenceSubscriber(event_store=self.event_store)

    def close(self):
        self.persistence_subscriber.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
