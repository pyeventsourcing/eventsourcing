from collections import namedtuple
from uuid import UUID

from cassandra.cqlengine import columns

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.example.domainmodel import create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy
from eventsourcing.infrastructure.cassandra.datastore import ActiveRecord, CassandraDatastore, CassandraSettings
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase

# In this test the default SequencedItem class is replaced with a "stored event" class.
# How easy is it to customize the infrastructure to support that? We just need
# to define the new sequenced item class, define a suitable active record class,
# and configure the other components. It's easy.


StoredEvent = namedtuple('StoredEvent', ['aggregate_id', 'aggregate_version', 'event_type', 'state'])


class StoredEventRecord(ActiveRecord):
    """Stores integer-sequenced items in Cassandra."""
    __table_name__ = 'integer_sequenced_items'
    _if_not_exists = True

    # Aggregate ID (e.g. an entity or aggregate ID).
    aggregate_id = columns.UUID(partition_key=True)

    # Aggregate version (index) of item in sequence.
    aggregate_version = columns.BigInt(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    event_type = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    state = columns.Text(required=True)


class ExampleApplicationWithAlternativeSequencedItemType(object):
    def __init__(self):
        self.event_store = EventStore(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=StoredEventRecord,
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
        self.datastore.drop_connection()
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
            all_records = list(app.event_store.active_record_strategy.all_records())
            assert len(all_records) == 1
            stored_event = all_records[0]
            assert stored_event.aggregate_id == entity1.id
            assert stored_event.aggregate_version == 0

            # Todo: Finish this off so we can read events.
            # Read entity from repo.
            retrieved_obj = app.repository[entity1.id]
            self.assertEqual(retrieved_obj.id, entity1.id)
