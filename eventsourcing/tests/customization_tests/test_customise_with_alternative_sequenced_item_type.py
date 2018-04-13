from uuid import UUID

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.example.domainmodel import create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord, Base
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase


# This test replaces the default SequencedItem class with a StoredEvent class.
# How easy is it to customize the infrastructure to support that? We just need
# to define the new sequenced item class, define a suitable record class,
# and configure the other components. It's easy.


class ExampleApplicationWithAlternativeSequencedItemType(object):
    def __init__(self, session):
        self.event_store = EventStore(
            record_manager=SQLAlchemyRecordManager(
                session=session,
                record_class=StoredEventRecord,
                sequenced_item_class=StoredEvent,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=StoredEvent,
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version',
            )
        )
        self.repository = ExampleRepository(
            event_store=self.event_store,
        )
        self.persistence_policy = PersistencePolicy(self.event_store)

    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TestExampleWithAlternativeSequencedItemType(AbstractDatastoreTestCase):
    def setUp(self):
        super(TestExampleWithAlternativeSequencedItemType, self).setUp()
        self.datastore.setup_connection()
        self.datastore.drop_tables()  # something isn't dropping tables...
        self.datastore.setup_tables()

    def tearDown(self):
        self.datastore.drop_tables()
        self.datastore.close_connection()
        super(TestExampleWithAlternativeSequencedItemType, self).setUp()

    def construct_datastore(self):
        return SQLAlchemyDatastore(
            base=Base,
            settings=SQLAlchemySettings(),
            tables=(StoredEventRecord,)
        )

    def _test(self):
        with ExampleApplicationWithAlternativeSequencedItemType(self.datastore.session) as app:
            # Create entity.
            entity1 = create_new_example(a='a', b='b')
            self.assertIsInstance(entity1.id, UUID)
            self.assertEqual(entity1.a, 'a')
            self.assertEqual(entity1.b, 'b')

            # Check there is a stored event.
            all_records = list(app.event_store.record_manager.get_notifications())
            self.assertEqual(1, len(all_records))
            stored_event = all_records[0]
            self.assertEqual(stored_event.originator_id, entity1.id)
            self.assertEqual(stored_event.originator_version, 0)

            # Read entity from repo.
            retrieved_obj = app.repository[entity1.id]
            self.assertEqual(retrieved_obj.id, entity1.id)
