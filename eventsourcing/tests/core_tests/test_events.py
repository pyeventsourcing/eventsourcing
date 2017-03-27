import unittest
from time import time
from uuid import UUID, uuid4

from eventsourcing.domain.model.decorators import subscribe_to
from eventsourcing.domain.model.events import DomainEvent, EventWithEntityID, EventHandlersNotEmptyError, \
    EventWithEntityVersion, EventWithTimestamp, TimestampedEntityEvent, VersionedEntityEvent, _event_handlers, \
    all_events, assert_event_handlers_empty, create_timesequenced_event_id, publish, resolve_domain_topic, subscribe, \
    unsubscribe
from eventsourcing.example.domainmodel import Example
from eventsourcing.exceptions import TopicResolutionError

try:
    from unittest import mock
except ImportError:
    import mock


class TestAbstractDomainEvent(unittest.TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(DomainEvent):
            pass

        # Check subclass can be instantiated.
        event1 = Event()
        self.assertEqual(event1.__always_encrypt__, False)

        # Check subclass can be instantiated with other parameters.
        event2 = Event(name='value')

        # Check the attribute value is available.
        self.assertEqual(event2.name, 'value')

        # Check the attribute value cannot be changed
        with self.assertRaises(AttributeError):
            event2.name = 'another value'
        self.assertEqual(event2.name, 'value')

        # Check it's equal to itself, by value.
        self.assertEqual(event2, event2)
        self.assertEqual(event2, Event(name='value'))

        # Check not equal to same event type with different values.
        self.assertNotEqual(event2, Event(name='another value'))

        # Check not equal to different type with same values.
        class SubclassEvent(Event):
            pass

        self.assertNotEqual(event2, SubclassEvent(name='value'))


class TestEntityEvent(unittest.TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithEntityID):
            pass

        # Check can't instantiate without an ID.
        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            Event()

        # Check any kind of ID is acceptable.
        event = Event(entity_id='1')
        self.assertEqual(event.entity_id, '1')

        event = Event(entity_id=1)
        self.assertEqual(event.entity_id, 1)

        event = Event(entity_id=uuid4())
        self.assertIsInstance(event.entity_id, UUID)

        # Check the ID value can't be reassigned.
        with self.assertRaises(AttributeError):
            # noinspection PyPropertyAccess
            event.entity_id = '2'


class TestTimestampEvent(unittest.TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithTimestamp):
            pass

        # Check event can be instantiated with a timestamp.
        time1 = time()
        event = Event(timestamp=time1)
        self.assertEqual(event.timestamp, time1)

        # Check event can be instantiated without a timestamp.
        event = Event()
        self.assertGreater(event.timestamp, time1)
        self.assertLess(event.timestamp, time())

        # Check the timestamp value can't be reassigned.
        with self.assertRaises(AttributeError):
            # noinspection PyPropertyAccess
            event.timestamp = time()


class TestVersionEvent(unittest.TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithEntityVersion):
            pass

        # Check event can be instantiated with a version.
        version1 = 1
        event = Event(entity_version=version1)
        self.assertEqual(event.entity_version, version1)

        # Check event can't be instantiated without a version.
        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            event = Event()

        # Check version must be an integer.
        with self.assertRaises(TypeError):
            event = Event(entity_version='1')

        # Check the version value can't be reassigned.
        with self.assertRaises(AttributeError):
            # noinspection PyPropertyAccess
            event.entity_version = 2


class TestVersionEntityEvent(unittest.TestCase):
    # noinspection PyArgumentList
    def test(self):
        # Check base class can be sub-classed.
        class Event(VersionedEntityEvent):
            pass

        # Check construction requires both an ID and version.
        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            Event()

        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            Event(entity_id='1')

        with self.assertRaises(TypeError):
            Event(entity_version=1)

        event1 = Event(entity_id='1', entity_version=0)

        event2 = Event(entity_id='1', entity_version=1)

        # Check the event attributes.
        self.assertEqual(event1.entity_id, '1')
        self.assertEqual(event2.entity_id, '1')
        self.assertEqual(event1.entity_version, 0)
        self.assertEqual(event2.entity_version, 1)

        # Check the events are not equal to each other, whilst being equal to themselves.
        self.assertEqual(event1, event1)
        self.assertEqual(event2, event2)
        self.assertNotEqual(event1, event2)


class TestTimestampEntityEvent(unittest.TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(TimestampedEntityEvent):
            pass

        # Check construction requires an ID.
        with self.assertRaises(TypeError):
            Event()

        # Get timestamp before events.
        time1 = time()

        # Construct events.
        event1 = Event(entity_id='1')
        event2 = Event(entity_id='1')

        # Check the entity IDs.
        self.assertEqual(event1.entity_id, '1')
        self.assertEqual(event2.entity_id, '1')

        # Check the event timestamps.
        self.assertLess(time1, event1.timestamp)
        self.assertLess(event1.timestamp, event2.timestamp)
        self.assertLess(event2.timestamp, time())

        # Check the events are not equal to each other, whilst being equal to themselves.
        self.assertEqual(event1, event1)
        self.assertEqual(event2, event2)
        self.assertNotEqual(event1, event2)


class TestTimeSequencedEvent(unittest.TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(TimestampedEntityEvent):
            pass

        class Event2(TimestampedEntityEvent):
            pass

        # Check subclass can be instantiated with 'entity_id' parameter.
        ID1 = uuid4()
        ID2 = uuid4()
        VALUE1 = 'a string'
        VALUE2 = 'another string'
        event1 = Event(
            entity_id=ID1,
        )
        self.assertEqual(event1.entity_id, ID1)

        # Check event has a domain event ID, and a timestamp.
        self.assertTrue(event1.timestamp)
        self.assertIsInstance(event1.timestamp, float)

        # Check subclass can be instantiated with 'timestamp' parameter.
        DOMAIN_EVENT_ID1 = create_timesequenced_event_id()
        event2 = Event(
            entity_id=ID1,
            timestamp=DOMAIN_EVENT_ID1,
        )
        self.assertEqual(event2.timestamp, DOMAIN_EVENT_ID1)

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
            timestamp=event3.timestamp,
            an_attribute=VALUE1,
        )
        self.assertEqual(event3, event4)

        # Check domain events with same domain event ID have the same timestamp.
        event5 = Event(
            entity_id=event1.entity_id,
            timestamp=event1.timestamp,
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
        self.assertNotEqual(event2.timestamp, event4.timestamp)
        self.assertNotEqual(event2.timestamp, event4.timestamp)


# Todo: Review and reduce. This is the original test case, much but not all of which is covered by the new tests.
class TestEvents(unittest.TestCase):
    def tearDown(self):
        _event_handlers.clear()

    def test_event_attributes(self):
        entity_id1 = uuid4()
        event = Example.Created(entity_id=entity_id1, a=1, b=2)

        # Check constructor keyword args lead to read-only attributes.
        self.assertEqual(1, event.a)
        self.assertEqual(2, event.b)
        self.assertRaises(AttributeError, getattr, event, 'c')
        self.assertRaises(AttributeError, setattr, event, 'c', 3)

        # Check domain event has auto-generated timestamp.
        self.assertIsInstance(event.timestamp, float)

        # Check timestamp value can be given to domain events.
        event1 = Example.Created(entity_id=entity_id1, a=1, b=2, timestamp=3)
        self.assertEqual(3, event1.timestamp)

    def test_publish_subscribe_unsubscribe(self):
        # Check subscribing event handlers with predicates.
        # - when predicate is True, handler should be called
        event = mock.Mock()
        predicate = mock.Mock()
        handler = mock.Mock()

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

        # When predicate is True, handler should be called ONCE.
        subscribe(handler=handler, predicate=predicate)

        # Check we can assert there are event handlers subscribed.
        self.assertRaises(EventHandlersNotEmptyError, assert_event_handlers_empty)

        # Check what happens when an event is published.
        publish(event)
        predicate.assert_called_once_with(event)
        handler.assert_called_once_with(event)

        # When predicate is True, after unsubscribing, handler should NOT be called again.
        unsubscribe(handler=handler, predicate=predicate)
        publish(event)
        predicate.assert_called_once_with(event)
        handler.assert_called_once_with(event)

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

        # When predicate is False, handler should NOT be called.
        predicate = lambda x: False
        handler = mock.Mock()
        subscribe(handler=handler, predicate=predicate)
        publish(event)
        self.assertEqual(0, handler.call_count)

        # Unsubscribe.
        unsubscribe(handler=handler, predicate=predicate)

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

    def test_all_events(self):
        self.assertTrue(all_events(True))
        self.assertTrue(all_events(False))
        self.assertTrue(all_events(None))

    def test_hash(self):
        entity_id1 = uuid4()
        event1 = Example.Created(entity_id=entity_id1, a=1, b=2, timestamp=3)
        event2 = Example.Created(entity_id=entity_id1, a=1, b=2, timestamp=3)
        self.assertEqual(hash(event1), hash(event2))

    def test_equality_comparison(self):
        entity_id1 = uuid4()
        event1 = Example.Created(entity_id=entity_id1, a=1, b=2, timestamp=3)
        event2 = Example.Created(entity_id=entity_id1, a=1, b=2, timestamp=3)
        event3 = Example.Created(entity_id=entity_id1, a=3, b=2, timestamp=3)
        self.assertEqual(event1, event2)
        self.assertNotEqual(event1, event3)
        self.assertNotEqual(event2, event3)
        self.assertNotEqual(event2, None)

    def test_repr(self):
        entity_id1 = uuid4()
        event1 = Example.Created(entity_id=entity_id1, a=1, b=2, timestamp=3)
        self.assertEqual(
            "Example.Created(a=1, b=2, entity_id={}, entity_version=0, timestamp=3)".format(repr(entity_id1)),
            repr(event1)
        )

    def test_subscribe_to_decorator(self):
        entity_id1 = uuid4()
        event = Example.Created(entity_id=entity_id1, a=1, b=2)
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

    def test_topic_resolution_error(self):
        # Check topic resolution error is raised, if the module path is
        # broken, and if the class name is broken.
        resolve_domain_topic('eventsourcing.domain.model.events#DomainEvent')
        with self.assertRaises(TopicResolutionError):
            resolve_domain_topic('eventsourcing.domain.model.broken#DomainEvent')
        with self.assertRaises(TopicResolutionError):
            resolve_domain_topic('eventsourcing.domain.model.events#Broken')
