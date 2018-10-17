from uuid import uuid4

from eventsourcing.example.domainmodel import Example
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.utils.topic import get_topic


class TestEventStore(SQLAlchemyDatastoreTestCase):
    def setUp(self):
        super(TestEventStore, self).setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            self.datastore.setup_tables()

    def tearDown(self):
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.close_connection()
        super(TestEventStore, self).tearDown()

    def construct_event_store(self):
        event_store = EventStore(
            record_manager=self.factory.construct_integer_sequenced_record_manager(),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version'
            )
        )
        return event_store

    def test_get_domain_events(self):
        event_store = self.construct_event_store()

        # Check there are zero stored events in the repo.
        entity_id1 = uuid4()
        entity_events = event_store.get_domain_events(originator_id=entity_id1)
        entity_events = list(entity_events)
        self.assertEqual(0, len(entity_events))

        # Check there are zero events in the event store, using iterator.
        entity_events = event_store.get_domain_events(originator_id=entity_id1, page_size=1)
        entity_events = list(entity_events)
        self.assertEqual(0, len(entity_events))

        # Store a domain event.
        event1 = Example.Created(
            a=1, b=2,
            originator_id=entity_id1,
            originator_topic=get_topic(Example)
        )
        event_store.store(event1)

        # Check there is one event in the event store.
        entity_events = event_store.get_domain_events(originator_id=entity_id1)
        entity_events = list(entity_events)
        self.assertEqual(1, len(entity_events))

        # Check there are two events in the event store, using iterator.
        entity_events = event_store.get_domain_events(originator_id=entity_id1, page_size=1)
        entity_events = list(entity_events)
        self.assertEqual(1, len(entity_events))

        # Store another domain event.
        event1 = Example.AttributeChanged(
            a=1, b=2,
            originator_id=entity_id1,
            originator_version=1,
        )
        event_store.store(event1)

        # Check there are two events in the event store.
        entity_events = event_store.get_domain_events(originator_id=entity_id1)
        entity_events = list(entity_events)
        self.assertEqual(2, len(entity_events))

        # Check there are two events in the event store, using iterator.
        entity_events = event_store.get_domain_events(originator_id=entity_id1, page_size=1)
        entity_events = list(entity_events)
        self.assertEqual(2, len(entity_events))

    def test_get_most_recent_event(self):
        event_store = self.construct_event_store()

        # Check there is no most recent event.
        entity_id1 = uuid4()
        entity_event = event_store.get_most_recent_event(originator_id=entity_id1)
        self.assertEqual(entity_event, None)

        # Store a domain event.
        event1 = Example.Created(
            a=1,
            b=2,
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
        )
        event_store.store(event1)

        # Check there is an event.
        entity_event = event_store.get_most_recent_event(originator_id=entity_id1)
        self.assertEqual(entity_event, event1)

    def test_all_domain_events(self):
        event_store = self.construct_event_store()

        # Check there are zero domain events in total.
        domain_events = event_store.all_domain_events()
        domain_events = list(domain_events)
        self.assertEqual(len(domain_events), 0)

        # Store a domain event.
        entity_id1 = uuid4()
        event1 = Example.Created(
            a=1,
            b=2,
            originator_id=entity_id1,
            originator_topic=get_topic(Example)

        )
        event_store.store(event1)

        # Store another domain event for the same entity.
        event1 = Example.AttributeChanged(
            a=1, b=2,
            originator_id=entity_id1,
            originator_version=1,
            __previous_hash__=event1.__event_hash__,
        )
        event_store.store(event1)

        # Store a domain event for a different entity.
        entity_id2 = uuid4()
        event1 = Example.Created(
            originator_topic=get_topic(Example),
            originator_id=entity_id2,
            a=1, b=2,
        )
        event_store.store(event1)

        # Check there are three domain events in total.
        domain_events = event_store.all_domain_events()
        domain_events = list(domain_events)
        self.assertEqual(len(domain_events), 3)
