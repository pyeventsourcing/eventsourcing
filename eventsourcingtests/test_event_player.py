import unittest

from eventsourcing.infrastructure.event_sourced_repo import EventPlayer
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.base import InMemoryStoredEventRepository
from eventsourcing.domain.model.example import Example


class TestEventPlayer(unittest.TestCase):

    def test(self):
        stored_event_repo = InMemoryStoredEventRepository()
        event_store = EventStore(stored_event_repo)
        # Store example events.
        event1 = Example.Created(entity_id='entity1', timestamp=3, a=1, b=2)
        event2 = Example.Created(entity_id='entity2', timestamp=4, a=2, b=4)
        event3 = Example.Created(entity_id='entity3', timestamp=5, a=3, b=6)
        event4 = Example.Discarded(entity_id='entity3', timestamp=6, entity_version=1)
        event_store.append(event1)
        event_store.append(event2)
        event_store.append(event3)
        event_store.append(event4)
        # Check the event sourced entities are correct.
        # - just use a trivial mutator that always instantiates the 'Example'.
        event_player = EventPlayer(event_store=event_store, domain_class=Example)
        self.assertEqual('entity1', event_player['entity1'].id)
        self.assertEqual(1, event_player['entity1'].a)
        self.assertEqual(2, event_player['entity2'].a)

        # Check entity3 is not found.
        self.assertRaises(KeyError, event_player.__getitem__, 'entity3')
