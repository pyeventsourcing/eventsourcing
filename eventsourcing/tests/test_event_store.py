import unittest

from eventsourcing.domain.model.example import Example
from eventsourcing.domain.services.eventstore import EventStore
from eventsourcing.infrastructure.stored_event_repos.with_python_objects import PythonObjectsStoredEventRepository


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
