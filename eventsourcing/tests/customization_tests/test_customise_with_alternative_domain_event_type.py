from uuid import UUID, uuid4

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import TimeuuidedEntity
from eventsourcing.domain.model.events import EventWithTimeuuid, publish
from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy, \
    CqlTimeuuidSequencedItem
from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
from eventsourcing.tests.datastore_tests.test_cassandra import DEFAULT_KEYSPACE_FOR_TESTING
from eventsourcing.utils.time import timestamp_from_uuid


# This test has events with TimeUUID value as the 'event ID'. How easy is it to customize
# the infrastructure to support that? We just need to make a model that uses these events,
# define a suitable database table, and configure the other components. It's easy.

# Firstly, define and entity that uses events with TimeUUIDs.
class ExampleEntity(TimeuuidedEntity):
    def __init__(self, **kwargs):
        super(ExampleEntity, self).__init__(**kwargs)
        self._is_finished = False

    class Started(EventWithTimeuuid):
        pass

    class Finished(EventWithTimeuuid):
        pass

    def finish(self):
        event = ExampleEntity.Finished(
            originator_id=self.id,
        )
        self._apply_and_publish(event)

    @classmethod
    def _mutate(cls, initial, event):
        if isinstance(event, ExampleEntity.Started):
            return cls(**event.__dict__)
        elif isinstance(event, ExampleEntity.Finished):
            initial._is_finished = True
            return None

    @classmethod
    def start(cls):
        event = ExampleEntity.Started(originator_id=uuid4())
        entity = ExampleEntity._mutate(None, event)
        publish(event)
        return entity


# Define a suitable active record class.
#  - class CqlTimeuuidSequencedItem has been moved into the library

# Define an application that uses the entity class and the table
class ExampleApplicationWithTimeuuidSequencedItems(object):
    def __init__(self):
        self.event_store = EventStore(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlTimeuuidSequencedItem,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='originator_id',
                position_attr_name='event_id',
            )
        )
        self.repository = EventSourcedRepository(
            mutator=ExampleEntity._mutate,
            event_store=self.event_store,
        )
        self.persistence_policy = PersistencePolicy(self.event_store)

    def start_entity(self):
        return ExampleEntity.start()

    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TestDomainEventsWithTimeUUIDs(AbstractDatastoreTestCase):
    def setUp(self):
        super(TestDomainEventsWithTimeUUIDs, self).setUp()
        self.datastore.setup_connection()
        self.datastore.setup_tables()

    def tearDown(self):
        self.datastore.drop_tables()
        self.datastore.drop_connection()
        super(TestDomainEventsWithTimeUUIDs, self).setUp()

    def construct_datastore(self):
        return CassandraDatastore(
            settings=CassandraSettings(default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING),
            tables=(CqlTimeuuidSequencedItem,),
        )

    def test(self):
        with ExampleApplicationWithTimeuuidSequencedItems() as app:
            # Create entity.
            entity1 = app.start_entity()
            self.assertIsInstance(entity1._initial_event_id, UUID)
            expected_timestamp = timestamp_from_uuid(entity1._initial_event_id)
            self.assertEqual(entity1.created_on, expected_timestamp)
            self.assertTrue(entity1.last_modified_on, expected_timestamp)

            # Read entity from repo.
            retrieved_obj = app.repository[entity1.id]
            self.assertEqual(retrieved_obj.id, entity1.id)

            retrieved_obj.finish()
            assert retrieved_obj.id not in app.repository
