from typing import Tuple
from uuid import uuid4

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.example.domainmodel import Example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.tests.datastore_tests.test_cassandra import (
    CassandraDatastoreTestCase,
)
from eventsourcing.tests.datastore_tests.test_dynamodb import (
    DynamoDbDatastoreTestCase,
)
from eventsourcing.tests.datastore_tests.test_sqlalchemy import (
    SQLAlchemyDatastoreTestCase,
)
from eventsourcing.utils.topic import get_topic


class World(AggregateRoot):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history = []

    @property
    def history(self) -> Tuple:
        return tuple(self._history)

    def make_it_so(self, something) -> None:
        self.__trigger_event__(World.SomethingHappened, what=something)

    class SomethingHappened(AggregateRoot.Event):
        def mutate(self, obj):
            obj._history.append(self.what)


class EventSourcedRepositoryTestCase:
    def setUp(self):
        super().setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            self.datastore.drop_tables()
            self.datastore.setup_tables()

    def tearDown(self):
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.close_connection()
        super().tearDown()

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

    def test_get_and_project_events(self):
        """
        Test entity projections
        """
        # Setup an event store
        event_store = self.construct_event_store()

        # Setup persistence policy for subscription handler to write to datastore.
        policy = PersistencePolicy(
            event_store=event_store,
            persist_event_type=World.Event,
        )

        # Construct a repository.
        repository: EventSourcedRepository[
            World, World.Event
        ] = EventSourcedRepository(event_store=event_store)

        world = World.__create__()
        world.__save__()

        # Retrieve world from repository at different versions.
        assert world.id in repository
        world_copy = repository[world.id]

        world_copy_2 = repository.get_and_project_events(
            world.id, gt=0, initial_state=None
        )
        assert world_copy_2 is None

        world_copy_3 = repository.get_and_project_events(
            world.id, gte=0, initial_state=None
        )
        assert world_copy_3 == world_copy

        world_copy_4 = repository.get_and_project_events(
            world.id, gte=1, initial_state=None
        )
        assert world_copy_4 is None

        world_copy_5 = repository.get_and_project_events(
            world.id, lt=1, initial_state=None
        )
        assert world_copy_5 == world_copy

        world_copy_6 = repository.get_and_project_events(
            world.id, lt=0, initial_state=None
        )
        assert world_copy_6 is None

        world_copy_7 = repository.get_and_project_events(
            world.id, lte=0, initial_state=None
        )
        assert world_copy_7 == world_copy

        # Retrieve with limit
        world_copy_8 = repository.get_and_project_events(
            world.id, limit=1, initial_state=None
        )
        assert world_copy_8 == world_copy

        # Create multiple events and retrieve entity with query_ascending true
        world.make_it_so('something_changed')
        world.__save__()
        events = repository.event_store.list_events(world.id, is_ascending=True)
        assert len(events) == 2, events
        assert events[0].originator_version == 0

        # Retrieve entity with query_ascending false
        events = repository.event_store.list_events(world.id, is_ascending=False)
        assert len(events) == 2, events
        assert events[0].originator_version == 1

        # Check when results_ascending != query_ascending (True/False combo)
        items = event_store.record_manager.get_items(
            world.id,
            query_ascending=True,
            results_ascending=False,
        )
        items = list(items)
        assert len(items) == 2, items
        assert items[0].position == 1

        # Check when results_ascending != query_ascending (False/True combo)
        items = event_store.record_manager.get_items(
            world.id,
            query_ascending=False,
            results_ascending=True,
        )
        items = list(items)
        assert len(items) == 2, items
        assert items[0].position == 0

        # Retrieve projected entity up to last event (with gte 0 and no initial state)
        world_copy_9 = repository.get_and_project_events(
            world.id, gte=0, initial_state=None
        )
        assert world_copy_9 is not None
        assert world_copy_9 != world_copy

        # Retrieve projected entity up to last event (with gt 0 and initial state).
        # The projected entity should be same as above (with gte 0 and no initial state).
        world_copy_10 = repository.get_and_project_events(
            world.id, gt=0, initial_state=world_copy
        )
        assert world_copy_10 is not None
        assert world_copy_10 == world_copy_9

        # Retrieve projected entity up to last event (with lt 2 and no initial state)
        # The projected entity should be same as above (with gt 0 and initial state).
        world_copy_11 = repository.get_and_project_events(
            world.id, lt=2, initial_state=None
        )
        assert world_copy_11 is not None
        assert world_copy_11 == world_copy_9

        # Get record at position
        position = 1
        record = event_store.record_manager.get_record(world.id, position)
        assert record is not None
        assert record.position == position

        # Delete world
        world.__discard__()
        world.__save__()
        assert world.id not in repository, world
        try:
            # Repository raises key error.
            repository[world.id]
        except KeyError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Unsubscribe handlers
        policy.close()


class TestEventSourcedWithSQLAlchemyDataStore(
    EventSourcedRepositoryTestCase,
    SQLAlchemyDatastoreTestCase,
):
    pass


class TestEventSourcedWithCassandraDataStore(
    EventSourcedRepositoryTestCase,
    CassandraDatastoreTestCase,
):
    pass


class TestEventSourcedWithDynamoDbDataStore(
    EventSourcedRepositoryTestCase,
    DynamoDbDatastoreTestCase,
):
    pass
