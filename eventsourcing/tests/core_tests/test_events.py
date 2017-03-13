import unittest
from uuid import uuid1

from eventsourcing.utils.time import timestamp_from_uuid

try:
    from unittest import mock
except ImportError:
    import mock

from eventsourcing.domain.model.events import subscribe, publish, unsubscribe, assert_event_handlers_empty, \
    EventHandlersNotEmptyError, _event_handlers, IntegerSequencedDomainEvent, TimeSequencedDomainEvent, \
    create_timesequenced_event_id
from eventsourcing.domain.model.decorators import subscribe_to
from eventsourcing.example.domain_model import Example


class TestIntegerSequencedEvent(unittest.TestCase):

    def test(self):
        # Check base class can be sub-classed.
        class Event(IntegerSequencedDomainEvent):
            pass

        # Check subclass can be instantiated with 'entity_id'
        # and 'entity_version' parameters.
        VERSION_0 = 0
        VERSION1 = 1
        ID1 = 'entity1'
        ID2 = 'entity2'
        VALUE1 = 'a string'
        VALUE2 = 'another string'
        instance1 = Event(
            entity_id=ID1,
            entity_version=VERSION_0,
        )
        self.assertEqual(instance1.entity_id, ID1)
        self.assertEqual(instance1.entity_version, VERSION_0)

        # Check subclass can be instantiated with other parameters.
        instance2 = Event(
            entity_id=ID1,
            entity_version=VERSION_0,
            an_attribute=VALUE1,
        )

        # Check the attribute value is available.
        self.assertEqual(instance2.an_attribute, VALUE1)

        # Check the attribute value cannot be changed
        with self.assertRaises(AttributeError):
            instance2.an_attribute = VALUE2
        self.assertEqual(instance2.an_attribute, VALUE1)

        # Check the version is required to be an integer.
        with self.assertRaises(TypeError):
            ID_INVALID = 'invalid'
            Event(
                entity_id=ID1,
                entity_version=ID_INVALID,
            )

        # Check it's equal to itself.
        self.assertEqual(instance2, instance2)
        self.assertEqual(instance2, Event(
            entity_id=ID1,
            entity_version=VERSION_0,
            an_attribute=VALUE1,
        ))

        # Check it's not equal to same type but different values.
        self.assertNotEqual(instance2, Event(
            entity_id=ID1,
            entity_version=VERSION1,
            an_attribute=VALUE1,
        ))
        self.assertNotEqual(instance2, Event(
            entity_id=ID2,
            entity_version=VERSION_0,
            an_attribute=VALUE1,
        ))

        # Check it's not equal to instance of different type, with same values.
        class Event2(IntegerSequencedDomainEvent):
            pass

        self.assertNotEqual(instance2, Event2(
            entity_id=ID1,
            entity_version=VERSION_0,
            an_attribute=VALUE1,
        ))


class TestTimeSequencedEvent(unittest.TestCase):

    def test(self):
        # Check base class can be sub-classed.
        class Event(TimeSequencedDomainEvent):
            pass

        class Event2(TimeSequencedDomainEvent):
            pass

        # Check subclass can be instantiated with 'entity_id' parameter.
        ID1 = 'entity1'
        ID2 = 'entity2'
        VALUE1 = 'a string'
        VALUE2 = 'another string'
        event1 = Event(
            entity_id=ID1,
        )
        self.assertEqual(event1.entity_id, ID1)

        # Check event has a domain event ID, and a timestamp.
        self.assertTrue(event1.domain_event_id)
        self.assertIsInstance(event1.timestamp, float)

        # Check subclass can be instantiated with 'domain_event_id' parameter.
        DOMAIN_EVENT_ID1 = create_timesequenced_event_id()
        event2 = Event(
            entity_id=ID1,
            domain_event_id=DOMAIN_EVENT_ID1,
        )
        self.assertEqual(event2.domain_event_id, DOMAIN_EVENT_ID1)

        # Check subclass can be instantiated with other parameters.
        event3 = Event(
            entity_id=ID1,
            an_attribute=VALUE1,
        )
        self.assertEqual(event3.an_attribute, VALUE1)

        # Check the attribute value cannot be changed.
        with self.assertRaises(AttributeError):
            event3.an_attribute = VALUE2
        self.assertEqual(event3.an_attribute, VALUE1)

        # Check an event is equal to itself.
        self.assertTrue(event3 == event3)
        self.assertFalse(event3 != event3)
        event4 = Event(
            entity_id=ID1,
            domain_event_id=event3.domain_event_id,
            an_attribute=VALUE1,
        )
        self.assertEqual(event3, event4)

        # Check domain events with same domain event ID have the same timestamp.
        event5 = Event(
            entity_id=event1.entity_id,
            domain_event_id=event1.domain_event_id,
            an_attribute=VALUE1,
        )
        self.assertEqual(event1.timestamp, event5.timestamp)


        # Check it's not equal to different type with same values.
        self.assertFalse(event3 == Event2(
            entity_id=event3.entity_id,
            an_attribute=event3.an_attribute,
        ))
        self.assertTrue(event3 != Event2(
            entity_id=ID1,
            an_attribute=VALUE1,
        ))

        # Check it's not equal to same type with different values.
        # - different entity_id
        self.assertNotEqual(event3.entity_id, ID2)
        self.assertEqual(event3.an_attribute, VALUE1)
        self.assertFalse(event2 == Event(
            entity_id=ID2,
            an_attribute=VALUE1,
        ))
        # - different attribute value
        self.assertTrue(event2 != Event(
            entity_id=ID1,
            an_attribute=VALUE2,
        ))

        # Check domain events with different domain event IDs have different timestamps.
        event4 = Event(
            entity_id=ID1,
            an_attribute=VALUE1,
        )
        self.assertNotEqual(event2.domain_event_id, event4.domain_event_id)
        self.assertNotEqual(event2.timestamp, event4.timestamp)


class TestEvents(unittest.TestCase):
    def tearDown(self):
        _event_handlers.clear()

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
        self.assertEqual(timestamp_from_uuid(domain_event_id),
                         Example.Created(entity_id='entity1', a=1, b=2, domain_event_id=domain_event_id).timestamp)

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
        self.assertEqual(
            "Example.Created(a=1, b=2, domain_event_id=3, entity_id='entity1', entity_version=0)",
            repr(event1)
        )

    def test_subscribe_to_decorator(self):
        event = Example.Created(entity_id='entity1', a=1, b=2)
        handler = mock.Mock()

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

        @subscribe_to(Example.Created)
        def test_handler(e):
            handler(e)

        # Check we can assert there are event handlers subscribed.
        self.assertRaises(EventHandlersNotEmptyError, assert_event_handlers_empty)

        # Check what happens when an event is published.
        publish(event)
        handler.assert_called_once_with(event)
