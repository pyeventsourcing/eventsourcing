import unittest
from uuid import uuid1

from eventsourcing.utils.time import timestamp_from_uuid

try:
    from unittest import mock
except ImportError:
    import mock


from eventsourcing.domain.model.events import subscribe, publish, unsubscribe, assert_event_handlers_empty, \
    EventHandlersNotEmptyError
from eventsourcing.domain.model.example import Example


class TestEvents(unittest.TestCase):

    def test_event_attributes(self):
        event = Example.Created(entity_id='entity1', a=1, b=2)

        # Check constructor keyword args lead to read-only attributes.
        self.assertEqual(1, event.a)
        self.assertEqual(2, event.b)
        self.assertRaises(AttributeError, getattr, event, 'c')
        self.assertRaises(AttributeError, setattr, event, 'c', 3)

        # Check domain event has auto-generated timestamp.
        self.assertIsInstance(event.timestamp, float)

        # Check timestamp value can be given to domain events.
        self.assertEqual(3, Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=3).domain_event_id)
        domain_event_id = uuid1().hex
        self.assertEqual(timestamp_from_uuid(domain_event_id), Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=domain_event_id).timestamp)

    def test_publish_subscribe_unsubscribe(self):
        # Check subscribing event handlers with predicates.
        # - when predicate is True, handler should be called
        event = mock.Mock()
        predicate = mock.Mock()
        handler = mock.Mock()

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

        # When predicate is True, handler should be called ONCE.
        subscribe(event_predicate=predicate, subscriber=handler)

        # Check we can assert there are event handlers subscribed.
        self.assertRaises(EventHandlersNotEmptyError, assert_event_handlers_empty)

        # Check what happens when an event is published.
        publish(event)
        predicate.assert_called_once_with(event)
        handler.assert_called_once_with(event)

        # When predicate is True, after unsubscribing, handler should NOT be called again.
        unsubscribe(event_predicate=predicate, subscriber=handler)
        publish(event)
        predicate.assert_called_once_with(event)
        handler.assert_called_once_with(event)

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

        # When predicate is False, handler should NOT be called.
        predicate = lambda x: False
        handler = mock.Mock()
        subscribe(event_predicate=predicate, subscriber=handler)
        publish(event)
        self.assertEqual(0, handler.call_count)

        # Unsubscribe.
        unsubscribe(event_predicate=predicate, subscriber=handler)

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

    def test_hash(self):
        event1 = Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=3)
        event2 = Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=3)
        self.assertEqual(hash(event1), hash(event2))

    def test_equality_comparison(self):
        event1 = Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=3)
        event2 = Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=3)
        event3 = Example.Created(entity_id='entity1', a=3, b=2, domain_event_id=3)
        self.assertEqual(event1, event2)
        self.assertNotEqual(event1, event3)
        self.assertNotEqual(event2, event3)
        self.assertNotEqual(event2, None)

    def test_repr(self):
        event1 = Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=3)
        self.assertEqual("Example.Created(a=1, b=2, domain_event_id=3, entity_id='entity1', entity_version=0)", repr(event1))
