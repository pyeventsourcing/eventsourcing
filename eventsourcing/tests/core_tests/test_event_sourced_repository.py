from uuid import uuid4

from eventsourcing.example.domainmodel import Example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.tests.datastore_tests.test_sqlalchemy import (
    SQLAlchemyDatastoreTestCase,
)
from eventsourcing.utils.topic import get_topic


class TestEventSourcedRepository(SQLAlchemyDatastoreTestCase):
    def setUp(self):
        super(TestEventSourcedRepository, self).setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            self.datastore.setup_tables()

    def tearDown(self):
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.close_connection()
        super(TestEventSourcedRepository, self).tearDown()

    def construct_event_store(self):
        event_store = EventStore(
            record_manager=self.factory.construct_integer_sequenced_record_manager(),
            event_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name="originator_id",
                position_attr_name="originator_version",
            ),
        )
        return event_store

    def test_get_item(self) -> None:
        # Setup an event store.
        event_store = self.construct_event_store()

        # Put an event in the event store.
        entity_id = uuid4()
        event_store.store_events(
            [
                Example.Created(
                    a=1,
                    b=2,
                    originator_id=entity_id,
                    originator_topic=get_topic(Example),
                )
            ]
        )

        # Construct a repository.
        event_sourced_repo: EventSourcedRepository[
            Example, Example.Event
        ] = EventSourcedRepository(event_store=event_store)

        # Check the entity attributes.
        example = event_sourced_repo[entity_id]
        self.assertEqual(1, example.a)
        self.assertEqual(2, example.b)
        self.assertEqual(entity_id, example.id)

        # Check class-specific request.
        example = event_sourced_repo.get_instance_of(Example, entity_id)
        self.assertEqual(1, example.a)
        self.assertEqual(2, example.b)
        self.assertEqual(entity_id, example.id)

        # Check class-specific request fails on type.
        class SubExample(Example):
            pass

        self.assertIsNone(event_sourced_repo.get_instance_of(SubExample, entity_id))

        # Setup an example repository, using the subclass ExampleRepository.
        example_repo = ExampleRepository(event_store=event_store)

        # Check the repo has the example.
        self.assertIn(entity_id, example_repo)
        self.assertNotIn(uuid4(), example_repo)

        # Check the entity attributes.
        example = example_repo[entity_id]
        self.assertEqual(1, example.a)
        self.assertEqual(2, example.b)
        self.assertEqual(entity_id, example.id)
