from abc import ABCMeta

from six import with_metaclass

from eventsourcing.application.subscribers.persistence import PersistenceSubscriber
from eventsourcing.infrastructure.eventstore import EventStore, AbstractStoredEventRepository
from eventsourcing.infrastructure.transcoding import JSONStoredEventTranscoder


class ReadOnlyEventSourcingApplication(with_metaclass(ABCMeta)):

    def __init__(self, stored_event_repository=None, always_encrypt=False, cipher=None):
        """
        Constructs an event store using the given stored event repository.

        :param: stored_event_repository:  Repository containing stored events.

        :param always_encrypt:  Optional encryption of all stored events.

        :param cipher:  Used to decrypt (and possibly encrypt) stored events.

        """
        assert isinstance(stored_event_repository, AbstractStoredEventRepository)
        self.stored_event_repository = stored_event_repository
        self.event_store = self.create_event_store(always_encrypt, cipher)

    def create_event_store(self, always_encrypt=False, cipher=None):
        transcoder = self.create_transcoder(always_encrypt, cipher)
        event_store = EventStore(
            stored_event_repo=self.stored_event_repository,
            transcoder=transcoder,
        )
        return event_store

    def create_transcoder(self, always_encrypt=False, cipher=None):
        return JSONStoredEventTranscoder(always_encrypt=always_encrypt, cipher=cipher)

    def close(self):
        self.event_store = None
        self.stored_event_repository = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class EventSourcingApplication(ReadOnlyEventSourcingApplication):

    def __init__(self, **kwargs):
        super(EventSourcingApplication, self).__init__(**kwargs)
        self.persistence_subscriber = self.create_persistence_subscriber()

    def create_persistence_subscriber(self):
        return PersistenceSubscriber(
            event_store=self.event_store
        )

    def close(self):
        if self.persistence_subscriber is not None:
            self.persistence_subscriber.close()
            self.persistence_subscriber = None
        super(EventSourcingApplication, self).close()
