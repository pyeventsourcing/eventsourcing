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

    def __init__(self, integer_sequenced_event_store=None, timestamp_sequenced_event_store=None, snapshot_store=None):
        if integer_sequenced_event_store is not None:
            self.versioned_entity_event_policy = PersistencePolicy(
                event_store=integer_sequenced_event_store,
                event_type=VersionedEntityEvent,
            )
        else:
            self.versioned_entity_event_policy = None

        if timestamp_sequenced_event_store is not None:
            self.timestamped_entity_event_policy = PersistencePolicy(
                event_store=timestamp_sequenced_event_store,
                event_type=TimestampedEntityEvent,
            )
        else:
            self.timestamped_entity_event_policy = None

        if snapshot_store is not None:
            self.snapshot_policy = PersistencePolicy(
                event_store=snapshot_store,
                event_type=Snapshot,
            )
        else:
            self.snapshot_policy = None

    def close(self):
        if self.snapshot_policy:
            self.snapshot_policy.close()
        if self.timestamped_entity_event_policy:
            self.timestamped_entity_event_policy.close()
        if self.versioned_entity_event_policy:
            self.versioned_entity_event_policy.close()
