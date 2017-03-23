from uuid import UUID

from sqlalchemy.sql.schema import UniqueConstraint, Column, Sequence
from sqlalchemy.sql.sqltypes import Integer, Float, String, Text, BigInteger
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.example.domainmodel import register_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, Base, SQLAlchemySettings
from eventsourcing.infrastructure.transcoding import SequencedItemMapper
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase


class StoredEvent(tuple):
    __slots__ = ()

    _fields = ('aggregate_id', 'aggregate_version', 'event_type', 'timestamp', 'state')

    # noinspection PyInitNewSignature
    def __new__(cls, aggregate_id, aggregate_version, event_type, timestamp, state):
        return tuple.__new__(cls, (aggregate_id, aggregate_version, event_type, timestamp, state))

    @property
    def aggregate_id(self):
        return self[0]

    @property
    def aggregate_version(self):
        return self[1]

    @property
    def event_type(self):
        return self[2]

    @property
    def timestamp(self):
        return self[3]

    @property
    def state(self):
        return self[4]


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


class StoredEventMapper(SequencedItemMapper):

    def to_sequenced_item(self, domain_event):
        sequenced_item = super(StoredEventMapper, self).to_sequenced_item(domain_event)
        return StoredEvent(
            aggregate_id=domain_event.entity_id,
            aggregate_version=domain_event.entity_version,
            event_type=domain_event.__class__.__name__,
            timestamp=domain_event.timestamp,
            state=sequenced_item.data,
        )


class CustomActiveRecordStrategy(SQLAlchemyActiveRecordStrategy):

    def _to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        if isinstance(sequenced_item, list):
            return [self._to_active_record(i) for i in sequenced_item]
        return SqlStoredEvent(
            aggregate_id=sequenced_item.aggregate_id,
            aggregate_version=sequenced_item.aggregate_version,
            event_type=sequenced_item.event_type,
            timestamp=sequenced_item.timestamp,
            state=sequenced_item.state,
        )

    def _from_active_record(self, active_record):
        """
        Returns a sequenced item, from given active record.
        """
        return self.sequenced_item_class(
            aggregate_id=active_record.aggregate_id,
            aggregate_version=active_record.aggregate_version,
            event_type=active_record.event_type,
            timestamp=active_record.timestamp,
            state=active_record.state,
        )


class ExampleApplicationWithAlternativeSequencedItemType(object):
    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=CustomActiveRecordStrategy(
                datastore=datastore,
                active_record_class=SqlStoredEvent,

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
            all_records = list(app.event_store.active_record_strategy._filter())
            assert len(all_records) == 1
            stored_event = all_records[0]
            assert stored_event.aggregate_id == entity1.id
            assert stored_event.aggregate_version == 0

            # Todo: Finish this off so we can read events.
            # Read entity from repo.
            # retrieved_obj = app.repository[entity1.id]
            # self.assertEqual(retrieved_obj.id, entity1.id)


