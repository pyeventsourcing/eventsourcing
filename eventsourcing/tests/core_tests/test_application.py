from typing import Tuple
from unittest import TestCase

from eventsourcing.application.dynamodb import DynamoDbApplication
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.aggregate import AggregateRoot


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


class ApplicationTestCase:

    def setUp(self):
        super().setUp()
        self.app = self.construct_app(persist_event_type=World.Event)

    def tearDown(self):
        self.app.datastore.drop_tables()
        self.app.datastore.close_connection()
        super().tearDown()

    def test_get_and_project_events(self):
        """
        Test entity projections
        """
        with self.app as app:
            world = World.__create__()
            world.__save__()

            # Retrieve world from repository at different versions.
            world_copy = app.repository[world.id]
            assert world_copy.__version__ == world.__version__

            world_copy_2 = app.repository.get_and_project_events(
                world.id, gt=0, initial_state=None
            )
            assert world_copy_2 is None

            world_copy_3 = app.repository.get_and_project_events(
                world.id, gte=0, initial_state=None
            )
            assert world_copy == world_copy_3

            world_copy_4 = app.repository.get_and_project_events(
                world.id, gte=1, initial_state=None
            )
            assert world_copy_4 is None

            world_copy_5 = app.repository.get_and_project_events(
                world.id, lt=1, initial_state=None
            )
            assert world_copy == world_copy_5

            world_copy_6 = app.repository.get_and_project_events(
                world.id, lt=0, initial_state=None
            )
            assert world_copy_6 is None

            world_copy_7 = app.repository.get_and_project_events(
                world.id, lte=0, initial_state=None
            )
            assert world_copy == world_copy_7

            # Retrieve with limit
            world_copy_8 = app.repository.get_and_project_events(
                world.id, limit=1, initial_state=None
            )
            assert world_copy == world_copy_8

            # Create multiple events and retrieve entity with query_ascending true
            world.make_it_so('something_changed')
            world.__save__()
            events = app.repository.event_store.list_events(world.id, is_ascending=True)
            assert len(events) == 2, events
            assert events[0].originator_version == 0

            # Retrieve entity with query_ascending false
            events = app.repository.event_store.list_events(world.id, is_ascending=False)
            assert len(events) == 2, events
            assert events[0].originator_version == 1

            # Check when results_ascending != query_ascending (True/False combo)
            items = app.event_store.record_manager.get_items(
                world.id,
                query_ascending=True,
                results_ascending=False,
            )
            items = list(items)
            assert len(items) == 2, items
            assert items[0].originator_version == 1

            # Check when results_ascending != query_ascending (False/True combo)
            items = app.event_store.record_manager.get_items(
                world.id,
                query_ascending=False,
                results_ascending=True,
            )
            items = list(items)
            assert len(items) == 2, items
            assert items[0].originator_version == 0

            # Retrieve projected entity up to last event (with gte 0 and no initial state)
            world_copy_9 = app.repository.get_and_project_events(
                world.id, gte=0, initial_state=None
            )
            assert world_copy_9 is not None
            assert world_copy_9 != world_copy

            # Retrieve projected entity up to last event (with gt 0 and initial state).
            # The projected entity should be same as above (with gte 0 and no initial state).
            world_copy_10 = app.repository.get_and_project_events(
                world.id, gt=0, initial_state=world_copy
            )
            assert world_copy_10 is not None
            assert world_copy_10 == world_copy_9

            # Retrieve projected entity up to last event (with lt 2 and no initial state)
            # The projected entity should be same as above (with gt 0 and initial state).
            world_copy_11 = app.repository.get_and_project_events(
                world.id, lt=2, initial_state=None
            )
            assert world_copy_11 is not None
            assert world_copy_11 == world_copy_9

            # Get record at position
            position = 1
            record = app.event_store.record_manager.get_record(world.id, position)
            assert record is not None
            assert record.originator_version == position

            # Delete world
            world.__discard__()
            world.__save__()
            assert world.id not in app.repository, world
            try:
                # Repository raises key error.
                app.repository[world.id]
            except KeyError:
                pass
            else:
                raise Exception("Shouldn't get here")


class SQLAlchemyApplicationTestCase(TestCase):
    def construct_app(self, **kwargs):
        return SQLAlchemyApplication(**kwargs)


class TestAppWithSQLAlchemyApplication(
    ApplicationTestCase,
    SQLAlchemyApplicationTestCase,
):
    pass


class DynamoDbApplicationTestCase(TestCase):
    def construct_app(self, **kwargs):
        kwargs['wait_for_table'] = True
        return DynamoDbApplication(**kwargs)


class TestAppWithDynamoDbApplication(
    ApplicationTestCase,
    DynamoDbApplicationTestCase,
):
    pass
