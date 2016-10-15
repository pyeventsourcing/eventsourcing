import unittest
from eventsourcing.infrastructure.stored_events.python_objects_stored_events import PythonObjectsStoredEventRepository
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.domain.model.example import Example


class TestEventStore(unittest.TestCase):

    def test_get_entity_events(self):
        repo = PythonObjectsStoredEventRepository()
        event_store = EventStore(stored_event_repo=repo)

        # Check there are zero stored events in the repo.
        entity_events = event_store.get_entity_events(stored_entity_id='Example::entity1')
        entity_events = list(entity_events)
        self.assertEqual(0, len(entity_events))

        # Store a domain event.
        event1 = Example.Created(entity_id='entity1', a=1, b=2)
        event_store.append(event1)

        # Check there is one event in the event store.
        entity_events = event_store.get_entity_events(stored_entity_id='Example::entity1')
        entity_events = list(entity_events)
        self.assertEqual(1, len(entity_events))

        # Store another domain event.
        event1 = Example.AttributeChanged(entity_id='entity1', a=1, b=2, entity_version=1)
        event_store.append(event1)

        # Check there are two events in the event store.
        entity_events = event_store.get_entity_events(stored_entity_id='Example::entity1')
        entity_events = list(entity_events)
        self.assertEqual(2, len(entity_events))

        # Check there are two events in the event store.
        entity_events = event_store.get_entity_events(stored_entity_id='Example::entity1')
        entity_events = list(entity_events)
        self.assertEqual(2, len(entity_events))
