import unittest
from eventsourcing.infrastructure.stored_events.python_objects_stored_events import PythonObjectsStoredEventRepository
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.domain.model.example import Example


class TestEventStore(unittest.TestCase):

    def test_get_entity_events(self):
        repo = PythonObjectsStoredEventRepository()
        event_store = EventStore(stored_event_repo=repo)

        # Check there are zero stored events in the repo.
        entity_events = repo.get_entity_events(stored_entity_id='Example::entity1')
        self.assertEqual(0, len(entity_events))

        # Store a domain event.
        event1 = Example.Created(entity_id='entity1', a=1, b=2)
        event_store.append(event1)

        # Check there is one stored event in the repo.
        entity_events = repo.get_entity_events(stored_entity_id='Example::entity1')
        self.assertEqual(1, len(entity_events))

        # Store another domain event.
        event1 = Example.Created(entity_id='entity1', a=1, b=2)
        event_store.append(event1)

        # Check there are two stored events in the repo.
        entity_events = repo.get_entity_events(stored_entity_id='Example::entity1')
        self.assertEqual(2, len(entity_events))
