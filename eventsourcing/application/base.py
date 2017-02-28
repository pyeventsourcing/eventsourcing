from abc import ABCMeta

from six import with_metaclass

from eventsourcing.application.subscribers.persistence import PersistenceSubscriber
from eventsourcing.infrastructure.eventstore import EventStore, AbstractStoredEventRepository
from eventsourcing.infrastructure.transcoding import JSONTranscoder


class EventSourcingApplication(with_metaclass(ABCMeta)):
    persist_events = True

    def __init__(self, stored_event_repository=None, cipher=None,
                 always_encrypt_stored_events=False):
        """
        Initialises event sourcing application attributes. Constructs
        an event store using the given stored event repository, and
        optionally a persistence subscriber that uses the event store.

        To enable symmetric encryption of stored events, pass in a 'cipher' and
        provide a True value for 'always_encrypt_stored_events'.

        :param: stored_event_repository:  Saves and queryies stored events in a datastore.

        :param cipher:  Encrypts and decrypts domain event attributes.

        :param always_encrypt_stored_events:  Apply encryption to all domain events (requires cipher).

        """
        assert isinstance(stored_event_repository, AbstractStoredEventRepository)
        self.stored_event_repository = stored_event_repository
        self.event_store = self.create_event_store(
            cipher=cipher, always_encrypt=always_encrypt_stored_events
        )
        self.persistence_subscriber = self.create_persistence_subscriber()

    def create_event_store(self, cipher=None, always_encrypt=False):
        transcoder = self.create_transcoder(always_encrypt, cipher)
        return EventStore(
            stored_event_repo=self.stored_event_repository,
            transcoder=transcoder,
        )

    def create_transcoder(self, always_encrypt, cipher):
        return JSONTranscoder(
            cipher=cipher,
            always_encrypt=always_encrypt,
        )

    def create_persistence_subscriber(self):
        if self.persist_events and self.event_store:
            return PersistenceSubscriber(
                event_store=self.event_store
            )

    def close(self):
        if self.persistence_subscriber is not None:
            self.persistence_subscriber.close()
            self.persistence_subscriber = None
        self.event_store = None
        self.stored_event_repository = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
