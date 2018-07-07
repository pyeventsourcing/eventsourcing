from eventsourcing.domain.model.events import EventWithOriginatorVersion, subscribe, unsubscribe
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
        if self.event_type is None:
            return False
        if isinstance(event, (list, tuple)):
            return all(map(self.is_event, event))
        return isinstance(event, self.event_type)

    def store_event(self, event):
        self.event_store.append(event)

    def close(self):
        unsubscribe(self.store_event, self.is_event)


class SnapshottingPolicy(object):
    def __init__(self, repository, snapshot_store, persist_event_type=EventWithOriginatorVersion, period=2):
        self.repository = repository
        assert isinstance(snapshot_store, AbstractEventStore)
        self.snapshot_store = snapshot_store
        self.period = period
        self.persist_event_type = persist_event_type
        subscribe(predicate=self.condition, handler=self.take_snapshot)

    def close(self):
        unsubscribe(predicate=self.condition, handler=self.take_snapshot)

    def condition(self, event):
        # Periodically by default.
        if isinstance(event, (list, tuple)):
            for e in event:
                if self.condition(e):
                    return True
            else:
                return False
        else:
            if self.persist_event_type:
                if isinstance(event, self.persist_event_type):
                    return (event.originator_version + 1) % self.period == 0

    def take_snapshot(self, event):
        if isinstance(event, (list, tuple)):
            event = event[-1]  # snapshot at the last version
        self.repository.take_snapshot(event.originator_id, lte=event.originator_version)
