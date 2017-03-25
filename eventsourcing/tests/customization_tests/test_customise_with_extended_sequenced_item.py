from uuid import UUID

from sqlalchemy.sql.schema import UniqueConstraint, Column, Sequence
from sqlalchemy.sql.sqltypes import Integer, Float, String, Text, BigInteger
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.example.domainmodel import register_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, \
    SqlIntegerSequencedItem
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, Base, SQLAlchemySettings
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper, SequencedItem
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase


class ExtendedSequencedItem(SequencedItem):
    __slots__ = ()

    _fields = ('sequence_id', 'position', 'topic', 'data', 'timestamp', 'event_type')

    # noinspection PyInitNewSignature
    def __new__(cls, sequence_id, position, topic, data, timestamp, event_type):
        return tuple.__new__(cls, (sequence_id, position, topic, data, timestamp, event_type))

    @property
    def timestamp(self):
        return self[4]

    @property
    def event_type(self):
        return self[5]


class SqlExtendedIntegerSequencedItem(SqlIntegerSequencedItem):

    # Type of the event (class name).
    event_type = Column(String(100))

    # Timestamp of the event.
    timestamp = Column(Float())


class StoredEventMapper(SequencedItemMapper):

    def to_sequenced_item(self, domain_event):
        item = super(StoredEventMapper, self).to_sequenced_item(domain_event)
        return ExtendedSequencedItem(
            sequence_id=item.sequence_id,
            position=item.position,
            topic=item.topic,
            data=item.data,
            event_type=domain_event.__class__.__qualname__,
            timestamp=domain_event.timestamp,
        )


class CustomActiveRecordStrategy(SQLAlchemyActiveRecordStrategy):

    def to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        if isinstance(sequenced_item, list):
            return [self.to_active_record(i) for i in sequenced_item]
        return SqlExtendedIntegerSequencedItem(
            sequence_id=sequenced_item.sequence_id,
            position=sequenced_item.position,
            topic=sequenced_item.topic,
            data=sequenced_item.data,
            event_type=sequenced_item.event_type,
            timestamp=sequenced_item.timestamp,
        )

    def from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        return self.sequenced_item_class(
            sequence_id=active_record.sequence_id,
            position=active_record.position,
            topic=active_record.topic,
            data=active_record.data,
            event_type=active_record.event_type,
            timestamp=active_record.timestamp,
        )


class ExampleApplicationWithExtendedSequencedItemType(object):
    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=CustomActiveRecordStrategy(
                datastore=datastore,
                active_record_class=SqlExtendedIntegerSequencedItem,
                sequenced_item_class=ExtendedSequencedItem,

            ),
            sequenced_item_mapper=StoredEventMapper(
                position_attr_name='entity_version',
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


class TestExampleWithExtendedSequencedItemType(AbstractDatastoreTestCase):
    def setUp(self):
        super(TestExampleWithExtendedSequencedItemType, self).setUp()
        self.datastore.setup_connection()
        self.datastore.setup_tables()

    def tearDown(self):
        self.datastore.drop_tables()
        self.datastore.drop_connection()
        super(TestExampleWithExtendedSequencedItemType, self).setUp()

    def construct_datastore(self):
        return SQLAlchemyDatastore(
            base=Base,
            settings=SQLAlchemySettings(),
            tables=(SqlExtendedIntegerSequencedItem,),
        )

    def test(self):
        with ExampleApplicationWithExtendedSequencedItemType(self.datastore) as app:

            # Create entity.
            entity1 = register_new_example(a='a', b='b')
            self.assertIsInstance(entity1.id, UUID)
            self.assertEqual(entity1.a, 'a')
            self.assertEqual(entity1.b, 'b')

            # Check there is a stored event.
            all_records = list(app.event_store.active_record_strategy.filter())
            self.assertEqual(len(all_records), 1)
            active_record = all_records[0]
            self.assertEqual(active_record.sequence_id, entity1.id)
            self.assertEqual(active_record.position, 0)
            self.assertEqual(active_record.event_type, 'Example.Created', active_record.event_type)
            self.assertEqual(active_record.timestamp, entity1.created_on)

            # Read entity from repo.
            retrieved_obj = app.repository[entity1.id]
            self.assertEqual(retrieved_obj.id, entity1.id)


