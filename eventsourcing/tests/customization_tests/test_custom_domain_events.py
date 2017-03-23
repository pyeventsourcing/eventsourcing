from uuid import UUID, uuid4, uuid1

from cassandra.cqlengine.models import Model, columns

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import DomainEntity
from eventsourcing.domain.model.events import DomainEvent, EventWithEntityID, publish
from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy
from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.transcoding import SequencedItemMapper
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase, DEFAULT_KEYSPACE_FOR_TESTING
from eventsourcing.utils.time import timestamp_from_uuid


class EventWithTimeuuid(DomainEvent):
    """
    For events that have an timestamp attribute.
    """
    def __init__(self, event_id=None, **kwargs):
        super(EventWithTimeuuid, self).__init__(**kwargs)
        self.__dict__['event_id'] = event_id or uuid1()

    @property
    def event_id(self):
        return self.__dict__['event_id']


class Started(EventWithTimeuuid):
    pass


class Finished(EventWithTimeuuid):
    pass


class CustomEvent(EventWithTimeuuid, EventWithEntityID):
    pass


class TimeuuidedEntity(DomainEntity):
    def __init__(self, event_id=None, **kwargs):
        super(TimeuuidedEntity, self).__init__(**kwargs)
        self._initial_event_id = event_id
        self._last_event_id = event_id

    @property
    def created_on(self):
        return timestamp_from_uuid(self._initial_event_id)

    @property
    def last_modified_on(self):
        return timestamp_from_uuid(self._last_event_id)


class CustomEntity(TimeuuidedEntity, DomainEntity):
    pass


class CustomRepository(EventSourcedRepository):
    domain_class = CustomEntity


def mutate(entity, event):
    if isinstance(event, Started):
        entity = CustomEntity(**event.__dict__)
        return entity
    elif isinstance(event, Finished):
        entity._is_finished = True
        return entity


class CqlTimeuuidSequencedItem(Model):
    """Stores timeuid-sequenced items in Cassandra."""

    _if_not_exists = True

    __table_name__ = 'timeuuid_sequenced_items'

    # Sequence ID (e.g. an entity or aggregate ID).
    s = columns.UUID(partition_key=True)

    # Position (in time-uuid space) of item in sequence.
    p = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # Topic of the item (e.g. path to domain event class).
    t = columns.Text(required=True)

    # State of the item (serialized dict, possibly encrypted).
    d = columns.Text(required=True)


class CustomApplication(object):
    def __init__(self):
        self.event_store = EventStore(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlTimeuuidSequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                position_attr_name='event_id',
            )
        )
        self.custom_repository = CustomRepository(
            event_store=self.event_store,
        )
        self.persistence_policy = PersistencePolicy(self.event_store)

    def create_entity(self):
        event = Started(entity_id=uuid4())
        entity = mutate(None, event)
        publish(event)
        return entity

    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TestDomainEventsWithTimeUUIDs(AbstractDatastoreTestCase):
    def test(self):
        with CustomApplication() as app:
            entity1 = app.create_entity()
            self.assertIsInstance(entity1._initial_event_id, UUID)
            self.assertEqual(entity1.created_on, timestamp_from_uuid(entity1._initial_event_id))

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

