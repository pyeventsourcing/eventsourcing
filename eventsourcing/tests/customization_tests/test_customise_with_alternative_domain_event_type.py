from uuid import UUID

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import TimeuuidedEntity
from eventsourcing.domain.model.events import EventWithTimeuuid, DomainEvent
from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.cassandra.records import TimeuuidSequencedRecord
from eventsourcing.infrastructure.cassandra.manager import CassandraRecordManager
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
from eventsourcing.tests.datastore_tests.test_cassandra import DEFAULT_KEYSPACE_FOR_TESTING
from eventsourcing.utils.times import decimaltimestamp_from_uuid


# This test has events with TimeUUID value as the 'event ID'. How easy is it to customize
# the infrastructure to support that? We just need to make a model that uses these events,
# define a suitable database table, and configure the other components. It's easy.

# Firstly, define and entity that uses events with TimeUUIDs.


class ExampleEntity(TimeuuidedEntity):
    def __init__(self, **kwargs):
        super(ExampleEntity, self).__init__(**kwargs)
        self._is_finished = False

    class Started(TimeuuidedEntity.Created, EventWithTimeuuid):
        pass

    class Finished(EventWithTimeuuid, TimeuuidedEntity.Discarded):
        pass

    def finish(self):
        self.__trigger_event__(self.Finished)

    @classmethod
    def start(cls):
        return cls.__create__(event_class=ExampleEntity.Started)


# Define a suitable record class.
#  - class TimeuuidSequencedItem has been moved into the library

# Define an application that uses the entity class and the table
class ExampleApplicationWithTimeuuidSequencedItems(object):
    def __init__(self):
        self.event_store = EventStore(
            record_manager=CassandraRecordManager(
                record_class=TimeuuidSequencedRecord,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='originator_id',
                position_attr_name='event_id',
            )
        )
        self.repository = EventSourcedRepository(
            event_store=self.event_store,
        )
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store,
            persist_event_type=DomainEvent,
        )

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
        self.datastore.close_connection()
        super(TestDomainEventsWithTimeUUIDs, self).setUp()

    def construct_datastore(self):
        return CassandraDatastore(
            settings=CassandraSettings(default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING),
            tables=(TimeuuidSequencedRecord,),
        )

    def test(self):
        with ExampleApplicationWithTimeuuidSequencedItems() as app:
            # Create entity.
            entity1 = app.start_entity()
            self.assertIsInstance(entity1.___initial_event_id__, UUID)
            expected_timestamp = decimaltimestamp_from_uuid(entity1.___initial_event_id__)
            self.assertEqual(entity1.__created_on__, expected_timestamp)
            self.assertTrue(entity1.__last_modified__, expected_timestamp)

            # Read entity from repo.
            retrieved_obj = app.repository[entity1.id]
            self.assertEqual(retrieved_obj.id, entity1.id)

            retrieved_obj.finish()
            assert retrieved_obj.id not in app.repository
