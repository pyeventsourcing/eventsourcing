import unittest
from eventsourcing.infrastructure.event_player import EventPlayer
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events import InMemoryStoredEventRepository
from eventsourcingtests.test_domain_events import Example


class TestEventPlayer(unittest.TestCase):

    def test(self):
        stored_event_repo = InMemoryStoredEventRepository()
        event_store = EventStore(stored_event_repo)
        # Store example events.
        event1 = Example.Event(entity_id='entity1', timestamp=3, a=1, b=2)
        event2 = Example.Event(entity_id='entity2', timestamp=4, a=2, b=4)
        event3 = Example.Event(entity_id='entity3', timestamp=5, a=3, b=6)
        event4 = Example.Event(entity_id='entity3', timestamp=6, a=4, b=8)
        event_store.append(event1)
        event_store.append(event2)
        event_store.append(event3)
        event_store.append(event4)
        # Check the event sourced entities are correct.
        # - just use a trivial mutator that always instantiates the 'Example'.
        mutator = lambda entity, event: Example(event)
        event_player = EventPlayer(event_store=event_store, mutator=mutator)
        self.assertEqual('entity1', event_player['entity1'].id)
        self.assertEqual(1, event_player['entity1'].a)
        self.assertEqual(2, event_player['entity2'].a)

        # Check two events in same entity ID are played in correct order.
        self.assertEqual(8, event_player['entity3'].b)

        # Check non-registered entity ID causes a KeyError.
        self.assertRaises(KeyError, event_player.__getitem__, 'entity4')
