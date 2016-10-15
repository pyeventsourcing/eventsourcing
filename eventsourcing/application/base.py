from abc import abstractmethod, ABCMeta

from six import with_metaclass

from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber


class EventSourcingApplication(with_metaclass(ABCMeta)):
    persist_events = True

    def __init__(self, json_encoder_cls=None, json_decoder_cls=None, cipher=None,
                  always_encrypt_stored_events=False, check_expected_entity_versions=False):
        self.stored_event_repo = self.create_stored_event_repo(
            json_encoder_cls=json_encoder_cls,
            json_decoder_cls=json_decoder_cls,
            cipher=cipher,
            always_encrypt=always_encrypt_stored_events,
            check_expected_version=check_expected_entity_versions,
        )
        self.event_store = self.create_event_store()
        if self.persist_events:
            self.persistence_subscriber = self.create_persistence_subscriber()
        else:
            self.persistence_subscriber = None

    @abstractmethod
    def create_stored_event_repo(self, **kwargs):
        """Returns an instance of a subclass of StoredEventRepository.

        :rtype: StoredEventRepository
        """

    def create_event_store(self):
        return EventStore(self.stored_event_repo)

    def create_persistence_subscriber(self):
        return PersistenceSubscriber(self.event_store)

    def close(self):
        if self.persistence_subscriber:
            self.persistence_subscriber.close()
        self.stored_event_repo = None
        self.event_store = None
        self.persistence_subscriber = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
