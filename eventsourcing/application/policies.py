from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class PersistencePolicy(object):
    """
    Stores events of given type to given event store, whenever they are published.
    """

    def __init__(self, event_store, event_type=None):
        assert isinstance(event_store, AbstractEventStore), type(event_store)
        self.event_store = event_store
        self.event_type = event_type
        subscribe(self.store_event, self.is_event)

    def is_event(self, event):
        if isinstance(event, (list, tuple)):
            return all(map(self.is_event, event))
        return self.event_type is None or isinstance(event, self.event_type)

    def store_event(self, event):
        self.event_store.append(event)

    def close(self):
        unsubscribe(self.store_event, self.is_event)
