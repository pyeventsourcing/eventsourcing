from uuid import UUID

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.example.domainmodel import create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.cassandra.records import StoredEventRecord
from eventsourcing.infrastructure.cassandra.manager import CassandraRecordManager
from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase


# In this test the default SequencedItem class is replaced with a "stored event" class.
# How easy is it to customize the infrastructure to support that? We just need
# to define the new sequenced item class, define a suitable record class,
# and configure the other components. It's easy.

class ExampleApplicationWithAlternativeSequencedItemType(object):
    def __init__(self):
        self.event_store = EventStore(
            record_manager=CassandraRecordManager(
                record_class=StoredEventRecord,
                sequenced_item_class=StoredEvent,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=StoredEvent,
                other_attr_names=(),
            )
        )
        self.repository = ExampleRepository(
            event_store=self.event_store,
        )
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store,
            persist_event_type=DomainEvent
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.persistence_policy.close()


class TestExampleWithAlternativeSequencedItemType(AbstractDatastoreTestCase):
    def setUp(self):
        super(TestExampleWithAlternativeSequencedItemType, self).setUp()
        self.datastore.setup_connection()
        self.datastore.setup_tables()

    def tearDown(self):
        self.datastore.drop_tables()
        self.datastore.close_connection()
        super(TestExampleWithAlternativeSequencedItemType, self).setUp()

    def construct_datastore(self):
        return CassandraDatastore(
            settings=CassandraSettings(),
            tables=(StoredEventRecord,)

        )

    def test(self):
        with ExampleApplicationWithAlternativeSequencedItemType() as app:
            # Create entity.
            entity1 = create_new_example(a='a', b='b')
            self.assertIsInstance(entity1.id, UUID)
            self.assertEqual(entity1.a, 'a')
            self.assertEqual(entity1.b, 'b')

            # Check there is a stored event.
            all_records = list(app.event_store.record_manager.get_records(entity1.id))
            assert len(all_records) == 1, len(all_records)
            stored_event = all_records[0]
            assert isinstance(stored_event, StoredEventRecord), stored_event
            assert stored_event.originator_id == entity1.id
            assert stored_event.originator_version == 0

            # Read entity from repo.
            retrieved_obj = app.repository[entity1.id]
            self.assertEqual(retrieved_obj.id, entity1.id)
