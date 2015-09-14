import unittest

from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.base import InMemoryStoredEventRepository
from eventsourcing.domain.model.example import Example


class TestEventSourcedRepository(unittest.TestCase):

    def test(self):
        # Setup an event store.
        stored_event_repo = InMemoryStoredEventRepository()
        event_store = EventStore(stored_event_repo=stored_event_repo)

        # Put an event in the event store.
        entity_id = 'entity1'
        event_store.append(Example.Created(entity_id=entity_id, a=1, b=2))

        # Setup an example repository.
        example_repo = ExampleRepository(event_store=event_store)

        # Check the repo has the example.
        self.assertIn(entity_id, example_repo)
        self.assertNotIn('xxxxxxxx', example_repo)

        # Check the entity attributes.
        example = example_repo[entity_id]
        self.assertEqual(1, example.a)
        self.assertEqual(2, example.b)
        self.assertEqual(entity_id, example.id)
