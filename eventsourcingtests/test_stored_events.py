import unittest

from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.infrastructure.stored_events import serialize_domain_event, recreate_domain_event, \
    resolve_event_topic, StoredEvent, InMemoryEventRepository
from eventsourcingtests.test_domain_events import Example


class TestStoredEvent(unittest.TestCase):

    def test_serialize_domain_event(self):
        event1 = Example.Event(a=1, b=2, entity_id='entity1', timestamp=3)
        stored_event = serialize_domain_event(event1)
        self.assertEqual('entity1', stored_event.entity_id)
        self.assertEqual('eventsourcingtests.test_domain_events#Example.Event', stored_event.event_topic)
        self.assertEqual('{"a":1,"b":2,"entity_id":"entity1","timestamp":3}', stored_event.event_attrs)

    def test_recreate_domain_event(self):
        stored_event = StoredEvent(event_id='1',
                                   entity_id='entity1',
                                   event_topic='eventsourcingtests.test_domain_events#Example.Event',
                                   event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        domain_event = recreate_domain_event(stored_event)
        self.assertIsInstance(domain_event, Example.Event)
        self.assertEqual('entity1', domain_event.entity_id)
        self.assertEqual(1, domain_event.a)
        self.assertEqual(2, domain_event.b)
        self.assertEqual(3, domain_event.timestamp)

    def test_resolve_event_topic(self):
        example_topic = 'eventsourcingtests.test_domain_events#Example.Event'
        actual = resolve_event_topic(example_topic)
        self.assertEqual(Example.Event, actual)
        example_topic = 'xxxxxxxxxxxxx#Example.Event'
        self.assertRaises(TopicResolutionError, resolve_event_topic, example_topic)
        example_topic = 'eventsourcingtests.test_domain_events#Xxxxxxxx.Xxxxxxxx'
        self.assertRaises(TopicResolutionError, resolve_event_topic, example_topic)


class TestStoredEventRepository(unittest.TestCase):

    def test(self):
        stored_event_repo = InMemoryEventRepository()
        
        # Store an event for 'entity1'.
        stored_event1 = StoredEvent(event_id='1',
                                    entity_id='entity1',
                                    event_topic='eventsourcingtests.test_domain_events#Example.Event',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')

        # Append the event to the repo.
        stored_event_repo.append(stored_event1)

        # Check the repo contains the event.
        self.assertIn(stored_event1.event_id, stored_event_repo)  # __contains__
        self.assertIsInstance(stored_event_repo[stored_event1.event_id], StoredEvent)  # __getitem__

        # Store another event for 'entity1'.
        stored_event2 = StoredEvent(event_id='2',
                                    entity_id='entity1',
                                    event_topic='eventsourcingtests.test_domain_events#Example.Event',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":4}')
        stored_event_repo.append(stored_event2)

        # Get all events for 'entity1'.
        events = stored_event_repo.events_for_entity_id('entity1')
        self.assertEqual(2, len(events))
        first = events[0]
        self.assertIsInstance(first, StoredEvent)
        self.assertEqual(stored_event1.event_topic, first.event_topic)
        self.assertEqual(stored_event1.event_attrs, first.event_attrs)
