import os

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.random import decode_random_bytes
from eventsourcing.utils.uuids import uuid_from_application_name


class SimpleApplication(object):
    persist_event_type = None

    def __init__(self, name='', persistence_policy=None, persist_event_type=None, uri=None, pool_size=5, session=None,
                 cipher_key=None, sequenced_item_class=None, stored_event_record_class=None, setup_table=True,
                 contiguous_record_ids=True, pipeline_id=-1, notification_log_section_size=None):

        self.notification_log_section_size = notification_log_section_size
        self.name = name or type(self).__name__.lower()

        # Setup cipher (optional).
        self.setup_cipher(cipher_key)

        # Setup connection to database.
        self.setup_datastore(session, uri, pool_size)

        # Setup the event store.
        self.sequenced_item_class = sequenced_item_class or StoredEvent
        self.stored_event_record_class = stored_event_record_class
        self.contiguous_record_ids = contiguous_record_ids
        self.application_id = uuid_from_application_name(self.name)
        self.pipeline_id = pipeline_id
        self.setup_event_store()

        # Setup notifications.
        self.notification_log = RecordManagerNotificationLog(
            self.event_store.record_manager,
            section_size=self.notification_log_section_size
        )

        # Setup an event sourced repository.
        self.setup_repository()

        # Setup a persistence policy.
        self.persistence_policy = persistence_policy
        if self.persistence_policy is None:
            self.setup_persistence_policy(persist_event_type or type(self).persist_event_type)

        # Setup table in database.
        if setup_table and not session:
            self.setup_table()

    def change_pipeline(self, pipeline_id):
        self.pipeline_id = pipeline_id
        self.event_store.record_manager.pipeline_id = pipeline_id

    @property
    def session(self):
        return self.datastore.session

    def setup_cipher(self, cipher_key):
        cipher_key = decode_random_bytes(cipher_key or os.getenv('CIPHER_KEY', ''))
        self.cipher = AESCipher(cipher_key) if cipher_key else None

    def setup_datastore(self, session, uri, pool_size=5):
        from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
        self.datastore = SQLAlchemyDatastore(
            settings=SQLAlchemySettings(uri=uri, pool_size=pool_size),
            session=session,
        )

    def setup_event_store(self):
        # Construct event store.
        self.event_store = self.construct_event_store(self.application_id, self.pipeline_id)

    def construct_event_store(self, application_id, pipeline_id):
        sequenced_item_mapper = self.construct_sequenced_item_mapper()
        record_manager = self.construct_record_manager(application_id, pipeline_id)
        event_store = EventStore(
            record_manager=record_manager,
            sequenced_item_mapper=sequenced_item_mapper,
        )
        return event_store

    def construct_sequenced_item_mapper(self):
        sequenced_item_mapper = SequencedItemMapper(
            sequenced_item_class=self.sequenced_item_class,
            cipher=self.cipher,
            # sequence_id_attr_name=sequence_id_attr_name,
            # position_attr_name=position_attr_name,
            # json_encoder_class=json_encoder_class,
            # json_decoder_class=json_decoder_class,
        )
        return sequenced_item_mapper

    def construct_record_manager(self, application_id, pipeline_id):
        from eventsourcing.infrastructure.sqlalchemy.factory import SQLAlchemyInfrastructureFactory
        from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord
        factory = SQLAlchemyInfrastructureFactory(
            session=self.datastore.session,
            integer_sequenced_record_class=self.stored_event_record_class or StoredEventRecord,
            sequenced_item_class=(self.sequenced_item_class),
            contiguous_record_ids=(self.contiguous_record_ids),
            application_id=application_id,
            pipeline_id=pipeline_id,
        )
        record_manager = factory.construct_integer_sequenced_record_manager()
        return record_manager

    def setup_repository(self, **kwargs):
        event_store = self.event_store
        self.repository = self.construct_repository(event_store, **kwargs)

    def construct_repository(self, event_store, **kwargs):
        return EventSourcedRepository(
            event_store=event_store,
            **kwargs
        )

    def setup_persistence_policy(self, persist_event_type):
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store,
            event_type=persist_event_type
        )

    def setup_table(self):
        # Setup the database table using event store's record class.
        self.datastore.setup_table(
            self.event_store.record_manager.record_class
        )

    def drop_table(self):
        # Setup the database table using event store's record class.
        self.datastore.drop_table(
            self.event_store.record_manager.record_class
        )

    def close(self):
        # Close the persistence policy.
        if self.persistence_policy:
            self.persistence_policy.close()

        # Close database connection.
        self.datastore.close_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
