from eventsourcing.domain.model.events import TimestampedEntityEvent, VersionedEntityEvent, subscribe, unsubscribe
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class VersionedEntityPersistencePolicy(object):
    """
    Persists versioned entity events, whenever they are published.
    """
    def __init__(self, event_store=None):
        assert isinstance(event_store, AbstractEventStore)
        self.event_store = event_store
        subscribe(self.is_versioned_entity_event, self.store_versioned_entity_event)

    @staticmethod
    def is_versioned_entity_event(event):
        return isinstance(event, VersionedEntityEvent)

    def store_versioned_entity_event(self, event):
        self.event_store.append(event)

    def close(self):
        unsubscribe(self.is_versioned_entity_event, self.store_versioned_entity_event)


class TimestampedEntityPersistencePolicy(object):
    """
    Persists timestamped entity events, whenever they are published.
    """
    def __init__(self, event_store):
        assert isinstance(event_store, AbstractEventStore)
        self.event_store = event_store
        subscribe(self.is_timestamped_entity_event, self.store_timestamped_entity_event)

    @staticmethod
    def is_timestamped_entity_event(event):
        return isinstance(event, TimestampedEntityEvent)

    def store_timestamped_entity_event(self, event):
        self.event_store.append(event)

    def close(self):
        unsubscribe(self.is_timestamped_entity_event, self.store_timestamped_entity_event)


class CombinedPersistencePolicy(object):
    """
    Persists both timestamped and versioned entity events, whenever they are published.
    """

    def __init__(self, timestamped_entity_event_store, versioned_entity_event_store):
        self.timestamped_entity_policy =  TimestampedEntityPersistencePolicy(
            event_store=timestamped_entity_event_store
        )
        self.versioned_entity_policy =  VersionedEntityPersistencePolicy(
            event_store=versioned_entity_event_store
        )

    def close(self):
        self.timestamped_entity_policy.close()
        self.versioned_entity_policy.close()
