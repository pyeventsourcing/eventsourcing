from abc import ABCMeta

from six import with_metaclass

from eventsourcing.application.policies import PersistenceSubscriber, NewPersistenceSubscriber
from eventsourcing.infrastructure.eventstore import EventStore, AbstractStoredEventRepository, \
    AbstractSequencedItemRepository, NewEventStore
from eventsourcing.infrastructure.transcoding import JSONStoredEventTranscoder, SequencedItemMapper


class ReadOnlyEventSourcingApplication(with_metaclass(ABCMeta)):

    def __init__(self, stored_event_repository=None, always_encrypt=False, cipher=None):
        """
        Constructs an event store using the given stored event repository.

        :param: stored_event_repository:  Repository containing stored events.

        :param always_encrypt:  Optional encryption of all stored events.

        :param cipher:  Used to decrypt (and possibly encrypt) stored events.

        """
        assert isinstance(stored_event_repository, AbstractStoredEventRepository), stored_event_repository
        self.stored_event_repository = stored_event_repository
        self.event_store = self.construct_event_store(always_encrypt, cipher)

    def construct_event_store(self, always_encrypt=False, cipher=None):
        transcoder = self.construct_transcoder(always_encrypt, cipher)
        event_store = EventStore(
            stored_event_repo=self.stored_event_repository,
            transcoder=transcoder,
        )
        return event_store

    def construct_transcoder(self, always_encrypt=False, cipher=None):
        return JSONStoredEventTranscoder(always_encrypt=always_encrypt, cipher=cipher)

    def close(self):
        self.event_store = None
        self.stored_event_repository = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class EventSourcedApplication(ReadOnlyEventSourcingApplication):

    def __init__(self, **kwargs):
        super(EventSourcedApplication, self).__init__(**kwargs)
        self.persistence_subscriber = self.construct_persistence_subscriber()

    def construct_persistence_subscriber(self):
        return PersistenceSubscriber(
            event_store=self.event_store
        )

    def close(self):
        if self.persistence_subscriber is not None:
            self.persistence_subscriber.close()
            self.persistence_subscriber = None
        super(EventSourcedApplication, self).close()


class NewReadOnlyEventSourcingApplication(with_metaclass(ABCMeta)):

    def __init__(self, integer_sequenced_item_repository=None,
                 timestamp_sequenced_item_repository=None, always_encrypt=False, cipher=None):
        """
        Constructs an event store using the given stored event repository.

        :param: sequenced_item_repository:  Repository containing sequenced items.

        :param always_encrypt:  Optional encryption of persisted state.

        :param cipher:  Used to encrypt and decrypt stored events.

        """
        assert isinstance(integer_sequenced_item_repository, AbstractSequencedItemRepository), \
            type(integer_sequenced_item_repository)
        assert isinstance(timestamp_sequenced_item_repository, AbstractSequencedItemRepository), \
            type(integer_sequenced_item_repository)
        self.integer_sequenced_item_repository = integer_sequenced_item_repository
        self.timestamp_sequenced_item_repository = timestamp_sequenced_item_repository
        self.version_entity_event_store = self.construct_event_store(
            position_attr_name='entity_version',
            sequenced_item_repository=self.integer_sequenced_item_repository,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )
        self.timestamp_entity_event_store = self.construct_event_store(
            position_attr_name='timestamp',
            sequenced_item_repository=self.timestamp_sequenced_item_repository,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )

    def construct_event_store(self, position_attr_name, sequenced_item_repository, always_encrypt=False, cipher=None):
        sequenced_item_mapper = self.construct_sequenced_item_mapper(position_attr_name, always_encrypt, cipher)
        event_store = NewEventStore(
            sequenced_item_repository=sequenced_item_repository,
            sequenced_item_mapper=sequenced_item_mapper,
        )
        return event_store

    def construct_sequenced_item_mapper(self, position_attr_name, always_encrypt=False, cipher=None):
        return SequencedItemMapper(position_attr_name, always_encrypt=always_encrypt, cipher=cipher)

    def close(self):
        self.event_store = None
        self.integer_sequenced_item_repository = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class NewEventSourcedApplication(NewReadOnlyEventSourcingApplication):

    def __init__(self, **kwargs):
        super(NewEventSourcedApplication, self).__init__(**kwargs)
        self.persistence_subscriber = self.construct_persistence_subscriber()

    def construct_persistence_subscriber(self):
        return NewPersistenceSubscriber(
            version_entity_event_store=self.version_entity_event_store,
            timestamp_entity_event_store=self.timestamp_entity_event_store,
        )

    def close(self):
        if self.persistence_subscriber is not None:
            self.persistence_subscriber.close()
            self.persistence_subscriber = None
        super(NewEventSourcedApplication, self).close()
