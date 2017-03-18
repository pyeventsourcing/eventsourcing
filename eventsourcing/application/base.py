from abc import ABCMeta

from six import with_metaclass

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.transcoding import SequencedItemMapper


class ReadOnlyEventSourcingApplication(with_metaclass(ABCMeta)):

    def __init__(self, integer_sequenced_active_record_strategy=None,
                 timestamp_sequenced_active_record_strategy=None, always_encrypt=False, cipher=None):
        """
        Constructs an event store using the given stored event repository.

        :param: sequenced_item_repository:  Repository containing sequenced items.

        :param always_encrypt:  Optional encryption of persisted state.

        :param cipher:  Used to encrypt and decrypt stored events.

        """
        assert isinstance(integer_sequenced_active_record_strategy, AbstractActiveRecordStrategy), \
            type(integer_sequenced_active_record_strategy)

        assert isinstance(timestamp_sequenced_active_record_strategy, AbstractActiveRecordStrategy), \
            type(integer_sequenced_active_record_strategy)

        self.integer_sequenced_active_record_strategy = integer_sequenced_active_record_strategy
        self.timestamp_sequenced_active_record_strategy = timestamp_sequenced_active_record_strategy
        self.version_entity_event_store = self.construct_event_store(
            position_attr_name='entity_version',
            active_record_strategy=self.integer_sequenced_active_record_strategy,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )
        self.timestamp_entity_event_store = self.construct_event_store(
            position_attr_name='timestamp',
            active_record_strategy=self.timestamp_sequenced_active_record_strategy,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )

    def construct_event_store(self, position_attr_name, active_record_strategy, always_encrypt=False, cipher=None):
        sequenced_item_mapper = self.construct_sequenced_item_mapper(position_attr_name, always_encrypt, cipher)
        event_store = EventStore(
            active_record_strategy=active_record_strategy,
            sequenced_item_mapper=sequenced_item_mapper,
        )
        return event_store

    def construct_sequenced_item_mapper(self, position_attr_name, always_encrypt=False, cipher=None):
        return SequencedItemMapper(position_attr_name, always_encrypt=always_encrypt, cipher=cipher)

    def close(self):
        self.event_store = None
        self.integer_sequenced_active_record_strategy = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class EventSourcedApplication(ReadOnlyEventSourcingApplication):

    def __init__(self, **kwargs):
        super(EventSourcedApplication, self).__init__(**kwargs)
        self.persistence_subscriber = self.construct_persistence_subscriber()

    def construct_persistence_subscriber(self):
        return PersistencePolicy(
            version_entity_event_store=self.version_entity_event_store,
            timestamp_entity_event_store=self.timestamp_entity_event_store,
        )

    def close(self):
        if self.persistence_subscriber is not None:
            self.persistence_subscriber.close()
            self.persistence_subscriber = None
        super(EventSourcedApplication, self).close()
