from collections import namedtuple
from uuid import UUID

from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Float, Integer, String, Text
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.example.domainmodel import register_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import Base, SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase

# This test replaces the default SequencedItem class with a StoredEvent class.
# How easy is it to customize the infrastructure to support that? We just need
# to define the new sequenced item class, define a suitable active record class,
# and configure the other components. It's easy.


StoredEvent = namedtuple('StoredEvent', ['aggregate_id', 'aggregate_version', 'event_type', 'state'])


class SqlStoredEvent(Base):
    # Explicit table name.
    __tablename__ = 'stored_events'

    # Unique constraint.
    __table_args__ = UniqueConstraint('aggregate_id', 'aggregate_version', name='stored_events_uc'),

    # Primary key.
    id = Column(Integer, Sequence('stored_event_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    aggregate_id = Column(UUIDType(), index=True)

    # Position (timestamp) of item in sequence.
    aggregate_version = Column(BigInteger(), index=True)

    # Type of the event (class name).
    event_type = Column(String(100))

    # Timestamp of the event.
    timestamp = Column(Float())

    # State of the item (serialized dict, possibly encrypted).
    state = Column(Text())


class ExampleApplicationWithAlternativeSequencedItemType(object):
    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=SqlStoredEvent,
                sequenced_item_class=StoredEvent,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=StoredEvent,
                event_sequence_id_attr='entity_id',
                event_position_attr='entity_version',
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
        self.datastore.setup_tables()

    def tearDown(self):
        self.datastore.drop_tables()
        self.datastore.drop_connection()
        super(TestExampleWithAlternativeSequencedItemType, self).setUp()

    def construct_datastore(self):
        return SQLAlchemyDatastore(
            base=Base,
            settings=SQLAlchemySettings(),
            tables=(SqlStoredEvent,),
        )

    def test(self):
        with ExampleApplicationWithAlternativeSequencedItemType(self.datastore) as app:
            # Create entity.
            entity1 = register_new_example(a='a', b='b')
            self.assertIsInstance(entity1.id, UUID)
            self.assertEqual(entity1.a, 'a')
            self.assertEqual(entity1.b, 'b')

            # Check there is a stored event.
            all_records = list(app.event_store.active_record_strategy.filter())
            assert len(all_records) == 1
            stored_event = all_records[0]
            assert stored_event.aggregate_id == entity1.id
            assert stored_event.aggregate_version == 0

            # Todo: Finish this off so we can read events.
            # Read entity from repo.
            retrieved_obj = app.repository[entity1.id]
            self.assertEqual(retrieved_obj.id, entity1.id)
