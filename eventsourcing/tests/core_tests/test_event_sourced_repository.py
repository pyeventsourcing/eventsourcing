from eventsourcing.example.new_domain_model import Example
from eventsourcing.example.infrastructure import ExampleRepo
from eventsourcing.infrastructure.eventstore import NewEventStore
from eventsourcing.infrastructure.transcoding import SequencedItemMapper
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    construct_integer_sequence_active_record_strategy


class TestEventSourcedRepository(SQLAlchemyDatastoreTestCase):

    def setUp(self):
        super(TestEventSourcedRepository, self).setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            self.datastore.setup_tables()

    def tearDown(self):
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.drop_connection()
        super(TestEventSourcedRepository, self).tearDown()

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

    def test_get_item(self):
        # Setup an event store.
        event_store = self.construct_event_store()

        # Put an event in the event store.
        entity_id = 'entity1'
        event_store.append(Example.Created(entity_id=entity_id, a=1, b=2))

        # Setup an example repository.
        example_repo = ExampleRepo(event_store=event_store)

        # Check the repo has the example.
        self.assertIn(entity_id, example_repo)
        self.assertNotIn('xxxxxxxx', example_repo)

        # Check the entity attributes.
        example = example_repo[entity_id]
        self.assertEqual(1, example.a)
        self.assertEqual(2, example.b)
        self.assertEqual(entity_id, example.id)
