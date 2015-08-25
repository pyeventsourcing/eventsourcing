import unittest

from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.infrastructure.stored_events import stored_event_from_domain_event, domain_event_from_stored_event, \
    resolve_event_topic, StoredEvent
from eventsourcingtests.test_domain_events import Example


class TestStoredEvent(unittest.TestCase):

    def test_stored_event_from_domain_event(self):
        event1 = Example.Event(a=1, b=2, entity_id='entity1', timestamp=3)
        stored_event = stored_event_from_domain_event(event1)
        self.assertEqual('entity1', stored_event.entity_id)
        self.assertEqual('eventsourcingtests.test_domain_events#Example.Event', stored_event.event_topic)
        self.assertEqual('{"a":1,"b":2,"entity_id":"entity1","timestamp":3}', stored_event.event_attrs)

    def test_domain_event_from_stored_event(self):
        stored_event = StoredEvent(entity_id='entity1',
                                   event_topic='eventsourcingtests.test_domain_events#Example.Event',
                                   event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        domain_event = domain_event_from_stored_event(stored_event)
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
