"""
:mod:`eventsourcing.application.policies` Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Persistance Policies

"""
from eventsourcing.domain.model.events import TimestampedEntityEvent, VersionedEntityEvent, subscribe, unsubscribe
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class PersistencePolicy(object):
    """
    Stores events of given type to given event store, whenever they are published.
    """
    def __init__(self, event_store, event_type=None):
        assert isinstance(event_store, AbstractEventStore)
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


class CombinedPersistencePolicy(object):
    """
    Persists both timestamped and versioned entity events, whenever they are published.
    """

    def __init__(self, timestamped_entity_event_store, versioned_entity_event_store, snapshot_store):
        self.timestamped_entity_event_policy = PersistencePolicy(
            event_store=timestamped_entity_event_store,
            event_type=TimestampedEntityEvent,
        )
        self.versioned_entity_event_policy = PersistencePolicy(
            event_store=versioned_entity_event_store,
            event_type=VersionedEntityEvent,
        )
        self.snapshot_policy = PersistencePolicy(
            event_store=snapshot_store,
            event_type=Snapshot,
        )

    def close(self):
        self.snapshot_policy.close()
        self.timestamped_entity_event_policy.close()
        self.versioned_entity_event_policy.close()
