from abc import abstractmethod, ABCMeta

from six import with_metaclass

from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber


class EventSourcingApplication(with_metaclass(ABCMeta)):
    persist_events = True

    def __init__(self, json_encoder_cls=None, json_decoder_cls=None, cipher=None, always_encrypt_stored_events=False,
                 always_check_expected_version=False, always_write_entity_version=False):
        """
        Initialises event sourcing application attributes. Constructs a stored event repo using a
        concrete method that must be provided by a subclass, an event store using the stored
        event repository, and optionally a persistence subscriber that uses the event store.

        As well as providing a concrete method to construct a stored event repository, subclasses
        may use the event store to construct event sourced repositories, from which event sourced
        entities can be retrieved. Subclasses may also construct other subscribers which excute
        commands against the entities in response to the publication of domain events.

        To enable symmetric encryption of stored events, pass in a 'cipher' and
        provide a True value for 'always_encrypt_stored_events'.

        To enable optimistic concurrency control (new in 1.1.0), pass a True value for argument
        'always_check_expected_version'. This feature depends on your having a table
        'entity_versions' is your schema, so if you are upgrading from v1.0.x of this package,
        then please check your schema and write a migration script for your application before
        deploying version 1.1.x into production.


        :param json_encoder_cls:  JSON encoder class.

        :param json_decoder_cls:  JSON decoder class.

        :param cipher:  Encryption cypher for encryption of event attributes when stored.

        :param always_encrypt_stored_events:  Apply encryption to all stored events.

        :param always_check_expected_version:  Concurrency errors whenever previous not found when writing new event.

        :param always_write_entity_version: Concurrency errors whenever version already exists when writing new event.
        """
        self.stored_event_repo = self.create_stored_event_repo(
            json_encoder_cls=json_encoder_cls, json_decoder_cls=json_decoder_cls,
            cipher=cipher, always_encrypt=always_encrypt_stored_events,
            always_check_expected_version=always_check_expected_version,
            always_write_entity_version=always_write_entity_version or always_check_expected_version,
        )
        self.event_store = self.create_event_store()
        self.persistence_subscriber = self.create_persistence_subscriber()

    @abstractmethod
    def create_stored_event_repo(self, **kwargs):
        """Returns an instance of a subclass of StoredEventRepository.

        :rtype: StoredEventRepository
        """

    def create_event_store(self):
        return EventStore(self.stored_event_repo)

    def create_persistence_subscriber(self):
        if self.persist_events and self.event_store:
            return PersistenceSubscriber(self.event_store)

    def close(self):
        if self.persistence_subscriber is not None:
            self.persistence_subscriber.close()
            self.persistence_subscriber = None
        self.event_store = None
        self.stored_event_repo = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
