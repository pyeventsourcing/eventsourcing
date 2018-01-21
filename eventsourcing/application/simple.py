import os

from eventsourcing.application.policies import PersistencePolicy, SnapshottingPolicy
from eventsourcing.domain.model.entity import DomainEntity
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import SnapshotRecord
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.random import decode_random_bytes


class SimpleApplication(object):
    def __init__(self, persist_event_type=None, uri=None, session=None, cipher_key=None,
                 stored_event_record_class=None, setup_table=True, contiguous_record_ids=True):

        # Setup cipher (optional).
        self.setup_cipher(cipher_key)

        # Setup connection to database.
        self.setup_datastore(session, uri)

        # Setup the event store.
        self.stored_event_record_class = stored_event_record_class
        self.contiguous_record_ids = contiguous_record_ids
        self.setup_event_store()

        # Setup notifications.
        self.notification_log = RecordManagerNotificationLog(
            self.event_store.record_manager,
            section_size=20,
        )

        # Setup an event sourced repository.
        self.setup_repository()

        # Setup a persistence policy.
        self.setup_persistence_policy(persist_event_type)

        # Setup table in database.
        if setup_table:
            self.setup_table()

    def setup_cipher(self, cipher_key):
        cipher_key = decode_random_bytes(cipher_key or os.getenv('CIPHER_KEY', ''))
        self.cipher = AESCipher(cipher_key) if cipher_key else None

    def setup_datastore(self, session, uri):
        self.datastore = SQLAlchemyDatastore(
            settings=SQLAlchemySettings(uri=uri),
            session=session,
        )

    def setup_event_store(self):
        # Construct event store.
        self.event_store = construct_sqlalchemy_eventstore(
            session=self.datastore.session,
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
        self.persistence_policy.close()

        # Close database connection.
        self.datastore.close_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class SnapshottingApplication(SimpleApplication):
    def __init__(self, period=10, snapshot_record_class=None, **kwargs):
        self.period = period
        self.snapshot_record_class = snapshot_record_class
        super(SnapshottingApplication, self).__init__(**kwargs)

    def setup_event_store(self):
        super(SnapshottingApplication, self).setup_event_store()
        # Setup snapshot store, using datastore session, and SnapshotRecord class.
        # Todo: Refactor this into a new create_sqlalchemy_snapshotstore() function.
        self.snapshot_store = EventStore(
            SQLAlchemyRecordManager(
                session=self.datastore.session,
                record_class=self.snapshot_record_class or SnapshotRecord
            ),
            SequencedItemMapper(
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version'
            )
        )

    def setup_repository(self, **kwargs):
        # Setup repository with a snapshot strategy.
        self.snapshot_strategy = EventSourcedSnapshotStrategy(
            event_store=self.snapshot_store
        )
        super(SnapshottingApplication, self).setup_repository(
            snapshot_strategy=self.snapshot_strategy, **kwargs
        )

    def setup_persistence_policy(self, persist_event_type):
        persist_event_type = persist_event_type or DomainEntity.Event
        super(SnapshottingApplication, self).setup_persistence_policy(persist_event_type)
        self.snapshotting_policy = SnapshottingPolicy(self.repository, self.period)
        self.snapshot_persistence_policy = PersistencePolicy(
            event_store=self.snapshot_store,
            event_type=Snapshot
        )

    def setup_table(self):
        super(SnapshottingApplication, self).setup_table()
        # Also setup snapshot table.
        self.datastore.setup_table(self.snapshot_store.record_manager.record_class)

    def close(self):
        super(SnapshottingApplication, self).close()
        self.snapshotting_policy.close()
        self.snapshot_persistence_policy.close()
