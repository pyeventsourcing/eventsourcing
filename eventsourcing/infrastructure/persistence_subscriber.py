from eventsourcing.domain.model.events import subscribe, DomainEvent, unsubscribe
from eventsourcing.infrastructure.event_store import EventStore


class PersistenceSubscriber(object):

    def __init__(self, event_store):
        assert isinstance(event_store, EventStore)
        self.event_store = event_store
        subscribe(self.is_domain_event, self.store_domain_event)

    @staticmethod
    def is_domain_event(event):
        return isinstance(event, DomainEvent)

    def store_domain_event(self, event):
        self.event_store.append(event)

    def close(self):
        unsubscribe(self.is_domain_event, self.store_domain_event)
