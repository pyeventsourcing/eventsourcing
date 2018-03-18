import os

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.infrastructure.django.datastore import DjangoDatastore, DjangoSettings
from eventsourcing.infrastructure.django.factory import construct_django_eventstore
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.random import decode_random_bytes


class DjangoApplication(object):
    def __init__(self, persist_event_type=None, cipher_key=None,
                 stored_event_record_class=None, contiguous_record_ids=True):
        # Setup cipher (optional).
        self.setup_cipher(cipher_key)

        # Setup connection to database.
        self.setup_datastore()

        # Setup the event store.
        self.stored_event_record_class = stored_event_record_class
        self.contiguous_record_ids = contiguous_record_ids
        self.setup_event_store()

        # Setup an event sourced repository.
        self.setup_repository()

        # Setup a persistence policy.
        self.setup_persistence_policy(persist_event_type)

    def setup_cipher(self, cipher_key):
        cipher_key = decode_random_bytes(cipher_key or os.getenv('CIPHER_KEY', ''))
        self.cipher = AESCipher(cipher_key) if cipher_key else None

    def setup_datastore(self):
        self.datastore = DjangoDatastore(
            settings=DjangoSettings(),
        )

    def setup_event_store(self):
        # Construct event store.

        self.event_store = construct_django_eventstore(
            cipher=self.cipher,
            record_class=self.stored_event_record_class,
            contiguous_record_ids=self.contiguous_record_ids,
        )

    def setup_repository(self, **kwargs):
        self.repository = EventSourcedRepository(
            event_store=self.event_store,
            **kwargs
        )

    def setup_persistence_policy(self, persist_event_type):
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store,
            event_type=persist_event_type
        )

    def close(self):
        # Close the persistence policy.
        self.persistence_policy.close()

        # Close database connection.
        self.datastore.close_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
