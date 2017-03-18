from eventsourcing.example.new_domain_model import Example
from eventsourcing.infrastructure.eventstore import NewEventStore
from eventsourcing.infrastructure.transcoding import SequencedItemMapper
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    construct_integer_sequence_active_record_strategy


class TestEventStore(SQLAlchemyDatastoreTestCase):

    def setUp(self):
        super(TestEventStore, self).setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            self.datastore.setup_tables()

    def tearDown(self):
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.drop_connection()
        super(TestEventStore, self).tearDown()

    def construct_event_store(self):
        event_store = NewEventStore(
            active_record_strategy=construct_integer_sequence_active_record_strategy(
                datastore=self.datastore,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                position_attr_name='entity_version'
            )
        )
        return event_store

    def test_get_domain_events(self):
        event_store = self.construct_event_store()

        # Check there are zero stored events in the repo.
        entity_events = event_store.get_domain_events(entity_id='entity1')
        entity_events = list(entity_events)
        self.assertEqual(0, len(entity_events))

        # Check there are zero events in the event store, using iterator.
        entity_events = event_store.get_domain_events(entity_id='entity1', page_size=1)
        entity_events = list(entity_events)
        self.assertEqual(0, len(entity_events))

        # Store a domain event.
        event1 = Example.Created(entity_id='entity1', a=1, b=2)
        event_store.append(event1)

        # Check there is one event in the event store.
        entity_events = event_store.get_domain_events(entity_id='entity1')
        entity_events = list(entity_events)
        self.assertEqual(1, len(entity_events))

        # Check there are two events in the event store, using iterator.
        entity_events = event_store.get_domain_events(entity_id='entity1', page_size=1)
        entity_events = list(entity_events)
        self.assertEqual(1, len(entity_events))

        # Store another domain event.
        event1 = Example.AttributeChanged(entity_id='entity1', a=1, b=2, entity_version=1)
        event_store.append(event1)

        # Check there are two events in the event store.
        entity_events = event_store.get_domain_events(entity_id='entity1')
        entity_events = list(entity_events)
        self.assertEqual(2, len(entity_events))

        # Check there are two events in the event store, using iterator.
        entity_events = event_store.get_domain_events(entity_id='entity1', page_size=1)
        entity_events = list(entity_events)
        self.assertEqual(2, len(entity_events))
