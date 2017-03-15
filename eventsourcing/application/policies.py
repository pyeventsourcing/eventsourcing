from eventsourcing.domain.model.events import NewDomainEvent, subscribe, unsubscribe, VersionEntityEvent, \
    TimestampEntityEvent
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class PersistenceSubscriber(object):
    def __init__(self, event_store):
        assert isinstance(event_store, AbstractEventStore)
        self.event_store = event_store
        subscribe(self.is_domain_event, self.store_domain_event)

    @staticmethod
    def is_domain_event(event):
        return isinstance(event, NewDomainEvent)

    def store_domain_event(self, event):
        self.event_store.append(event)

    def close(self):
        unsubscribe(self.is_domain_event, self.store_domain_event)


class AbstractPolicy(object):

    def __init__(self, *args, **kwargs):
        pass


class VersionEntityEventPersistence(AbstractPolicy):
    def __init__(self, version_entity_event_store=None, *args, **kwargs):
        super(VersionEntityEventPersistence, self).__init__(*args, **kwargs)
        assert isinstance(version_entity_event_store, AbstractEventStore)
        self.version_entity_event_store = version_entity_event_store
        subscribe(self.is_version_entity_event, self.store_version_entity_event)

    @staticmethod
    def is_version_entity_event(event):
        return isinstance(event, VersionEntityEvent)

    def store_version_entity_event(self, event):
        self.version_entity_event_store.append(event)

    def close(self):
        unsubscribe(self.is_version_entity_event, self.store_version_entity_event)


class TimestampEntityEventPersistence(AbstractPolicy):
    def __init__(self, timestamp_entity_event_store=None, *args, **kwargs):
        super(TimestampEntityEventPersistence, self).__init__(*args, **kwargs)
        assert isinstance(timestamp_entity_event_store, AbstractEventStore)
        self.timestamp_entity_event_store = timestamp_entity_event_store

        subscribe(self.is_timestamp_entity_event, self.store_timestamp_entity_event)

    @staticmethod
    def is_timestamp_entity_event(event):
        return isinstance(event, TimestampEntityEvent)

    def store_timestamp_entity_event(self, event):
        self.timestamp_entity_event_store.append(event)

    def close(self):
        unsubscribe(self.is_timestamp_entity_event, self.store_timestamp_entity_event)


class NewPersistenceSubscriber(VersionEntityEventPersistence, TimestampEntityEventPersistence):
    pass
