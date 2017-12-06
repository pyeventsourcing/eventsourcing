import os

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore
from eventsourcing.utils.random import decode_random_bytes


class SimpleApplication(object):
    def __init__(self, persist_event_type=None, **kwargs):
        # Setup the event store.
        self.setup_event_store(**kwargs)

        # Construct a persistence policy.
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store,
            event_type=persist_event_type
        )

        # Construct an event sourced repository.
        self.repository = EventSourcedRepository(
            event_store=self.event_store
        )

    def setup_event_store(self, uri=None, session=None, setup_table=True):
        # Setup connection to database.
        self.datastore = SQLAlchemyDatastore(
            settings=SQLAlchemySettings(uri=uri),
            session=session,
        )

        # Construct cipher (optional).
        aes_key = decode_random_bytes(os.getenv('AES_CIPHER_KEY', ''))
        cipher = AESCipher(aes_key) if aes_key else None

        # Construct event store.
        self.event_store = construct_sqlalchemy_eventstore(
            session=self.datastore.session,
            cipher=cipher,
        )

        # Setup table in database.
        if setup_table:
            self.setup_table()

    def setup_table(self):
        # Setup the database table using event store's active record class.
        self.datastore.setup_table(
            self.event_store.active_record_strategy.active_record_class
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
