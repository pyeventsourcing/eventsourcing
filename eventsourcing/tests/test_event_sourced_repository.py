import unittest

from eventsourcing.domain.model.example import Example
from eventsourcing.domain.services.eventstore import EventStore
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepo
from eventsourcing.infrastructure.stored_event_repos.with_python_objects import PythonObjectsStoredEventRepository


class TestEventSourcedRepository(unittest.TestCase):

    def test_get_item(self):
        # Setup an event store.
        stored_event_repo = PythonObjectsStoredEventRepository()
        event_store = EventStore(stored_event_repo=stored_event_repo)

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
