from decimal import Decimal
from typing import Dict
from uuid import UUID, uuid1, uuid4

from eventsourcing.domain.model.events import (
    DomainEvent,
    EventHandlersNotEmptyError,
    EventWithHash,
    EventWithOriginatorID,
    EventWithOriginatorVersion,
    EventWithTimestamp,
    EventWithTimeuuid,
    assert_event_handlers_empty,
    clear_event_handlers,
    create_timesequenced_event_id,
    publish,
    subscribe,
    unsubscribe,
)
from eventsourcing.example.domainmodel import Example
from eventsourcing.exceptions import EventHashError, TopicResolutionError
from eventsourcing.utils.times import decimaltimestamp, decimaltimestamp_from_uuid
from eventsourcing.utils.topic import get_topic, resolve_topic

try:
    from unittest import mock, TestCase
except ImportError:
    import mock


class Event(DomainEvent):
    pass


# Check not equal to different type with same values.
class SubclassEvent(Event):
    pass


class TestAbstractDomainEvent(TestCase):
    def test(self):
        # Check base class can be sub-classed.

        # Check subclass can be instantiated.
        event1 = Event()
        self.assertEqual(type(event1).__qualname__, "Event")

        # Check subclass can be instantiated with other parameters.
        event2 = Event(name="value")

        # Check the attribute value is available.
        self.assertEqual(event2.name, "value")

        # Check the attribute value cannot be changed
        with self.assertRaises(AttributeError):
            event2.name = "another value"
        self.assertEqual(event2.name, "value")

        # Check it's equal to itself, by value.
        self.assertEqual(event2, event2)
        self.assertEqual(event2, Event(name="value"))

        # Check not equal to same event type with different values.
        self.assertNotEqual(event2, Event(name="another value"))

        self.assertNotEqual(event2, SubclassEvent(name=event2.name))


class TestEventWithOriginatorID(TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithOriginatorID):
            pass

        # Check can't instantiate without an ID.
        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            Event()

        # Check any kind of ID is acceptable.
        event = Event(originator_id="1")
        self.assertEqual(event.originator_id, "1")

        event = Event(originator_id=1)
        self.assertEqual(event.originator_id, 1)

        event = Event(originator_id=uuid4())
        self.assertIsInstance(event.originator_id, UUID)

        # Check the ID value can't be reassigned.
        with self.assertRaises(AttributeError):
            # noinspection PyPropertyAccess
            event.originator_id = "2"


class TestEventWithOriginatorVersion(TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithOriginatorVersion):
            pass

        # Check event can be instantiated with a version.
        version1 = 1
        event = Event(originator_version=version1)
        self.assertEqual(event.originator_version, version1)

        # Check event can't be instantiated without a version.
        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            event = Event()

        # Check version must be an integer.
        with self.assertRaises(TypeError):
            event = Event(originator_version="1")

        # Check the version value can't be reassigned.
        with self.assertRaises(AttributeError):
            # noinspection PyPropertyAccess
            event.originator_version = 2


class TestEventWithTimestamp(TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithTimestamp):
            pass

        # Check event can be instantiated with a timestamp.
        time1 = decimaltimestamp()
        event = Event(timestamp=time1)
        self.assertEqual(event.timestamp, time1)

        # Check event can be instantiated without a timestamp.
        event = Event()
        self.assertGreaterEqual(event.timestamp, time1)
        self.assertLessEqual(event.timestamp, decimaltimestamp())

        # Check the timestamp value can't be reassigned.
        with self.assertRaises(AttributeError):
            # noinspection PyPropertyAccess
            event.timestamp = decimaltimestamp()


class TestEventWithTimeuuid(TestCase):
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithTimeuuid):
            pass

        # Check event has a UUID event_id.
        event = Event()
        self.assertIsInstance(event.event_id, UUID)

        # Check the event_id can't be reassigned.
        with self.assertRaises(AttributeError):
            # noinspection PyPropertyAccess
            event.event_id = decimaltimestamp()

        # Check event can be instantiated with a given UUID.
        event_id = uuid1()
        event = Event(event_id=event_id)
        self.assertEqual(event.event_id, event_id)

        # Generate a series of timestamps.
        events = [Event() for _ in range(100)]
        timestamps = [decimaltimestamp_from_uuid(e.event_id) for e in events]

        # Check series doesn't decrease at any point.
        last = timestamps[0]
        for timestamp in timestamps[1:]:
            self.assertLessEqual(last, timestamp)
            last = timestamp

        # Check last timestamp is greater than the first.
        self.assertGreater(timestamps[-1], timestamps[0])


class TestEventWithOriginatorVersionAndID(TestCase):
    # noinspection PyArgumentList
    def test(self):
        # Check base class can be sub-classed.
        class Event(EventWithOriginatorVersion, EventWithOriginatorID):
            pass

        # Check construction requires both an ID and version.
        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            Event()

        with self.assertRaises(TypeError):
            # noinspection PyArgumentList
            Event(originator_id="1")

        with self.assertRaises(TypeError):
            Event(originator_version=1)

        event1 = Event(originator_id="1", originator_version=0)

        event2 = Event(originator_id="1", originator_version=1)

        # Check the event attributes.
        self.assertEqual(event1.originator_id, "1")
        self.assertEqual(event2.originator_id, "1")
        self.assertEqual(event1.originator_version, 0)
        self.assertEqual(event2.originator_version, 1)

        # Check the events are not equal to each other, whilst being equal to
        # themselves.
        self.assertEqual(event1, event1)
        self.assertEqual(event2, event2)
        self.assertNotEqual(event1, event2)


class TestEventWithTimestampAndOriginatorID(TestCase):
    def test_one_subclass(self):
        # Check base class can be sub-classed.
        class Event(EventWithTimestamp, EventWithOriginatorID):
            pass

        # Check construction requires an ID.
        with self.assertRaises(TypeError):
            Event()

        # Get timestamp before events.
        time1 = decimaltimestamp()

        # Construct events.
        event1 = Event(originator_id="1")
        event2 = Event(originator_id="1")

        # Check the entity IDs.
        self.assertEqual(event1.originator_id, "1")
        self.assertEqual(event2.originator_id, "1")

        # Check the event timestamps.
        self.assertLessEqual(time1, event1.timestamp)
        self.assertLessEqual(event1.timestamp, event2.timestamp)
        self.assertLessEqual(event2.timestamp, decimaltimestamp())

        # Check the events are not equal to each other, whilst being equal to
        # themselves.
        self.assertEqual(event1, event1)
        self.assertEqual(event2, event2)
        self.assertNotEqual(event1, event2)

    def test_two_subclasses(self):
        # Check base class can be sub-classed.
        class Event(EventWithTimestamp, EventWithOriginatorID):
            pass

        class Event2(EventWithTimestamp, EventWithOriginatorID):
            pass

        # Check subclass can be instantiated with 'originator_id' parameter.
        ID1 = uuid4()
        ID2 = uuid4()
        VALUE1 = "a string"
        VALUE2 = "another string"
        event1 = Event(originator_id=ID1)
        self.assertEqual(event1.originator_id, ID1)

        # Check event has a domain event ID, and a timestamp.
        self.assertTrue(event1.timestamp)
        self.assertIsInstance(event1.timestamp, Decimal)

        # Check subclass can be instantiated with 'timestamp' parameter.
        DOMAIN_EVENT_ID1 = create_timesequenced_event_id()
        event2 = Event(originator_id=ID1, timestamp=DOMAIN_EVENT_ID1)
        self.assertEqual(event2.timestamp, DOMAIN_EVENT_ID1)

        # Check subclass can be instantiated with other parameters.
        event3 = Event(originator_id=ID1, an_attribute=VALUE1)
        self.assertEqual(event3.an_attribute, VALUE1)

        # Check the attribute value cannot be changed.
        with self.assertRaises(AttributeError):
            event3.an_attribute = VALUE2
        self.assertEqual(event3.an_attribute, VALUE1)

        # Check an event is equal to itself.
        self.assertTrue(event3 == event3)
        self.assertFalse(event3 != event3)
        event4 = Event(
            originator_id=ID1, timestamp=event3.timestamp, an_attribute=VALUE1
        )
        self.assertEqual(event3, event4)

        # Check domain events with same domain event ID have the same timestamp.
        event5 = Event(
            originator_id=event1.originator_id,
            timestamp=event1.timestamp,
            an_attribute=VALUE1,
        )
        self.assertEqual(event1.timestamp, event5.timestamp)

        # Check it's not equal to different type with same values.
        self.assertFalse(
            event3
            == Event2(
                originator_id=event3.originator_id, an_attribute=event3.an_attribute
            )
        )
        self.assertTrue(event3 != Event2(originator_id=ID1, an_attribute=VALUE1))

        # Check it's not equal to same type with different values.
        # - different originator_id
        self.assertNotEqual(event3.originator_id, ID2)
        self.assertEqual(event3.an_attribute, VALUE1)
        self.assertFalse(event2 == Event(originator_id=ID2, an_attribute=VALUE1))
        # - different attribute value
        self.assertTrue(event2 != Event(originator_id=ID1, an_attribute=VALUE2))

        # Check domain events with different domain event IDs have different timestamps.
        event4 = Event(originator_id=ID1, an_attribute=VALUE1)
        self.assertNotEqual(event2.timestamp, event4.timestamp)
        self.assertNotEqual(event2.timestamp, event4.timestamp)


# Todo: Review and reduce. This is the original test case, much but not all
#  of which is covered by the new tests above.
class TestEvents(TestCase):
    def tearDown(self):
        clear_event_handlers()

    def test_event_attributes(self):
        entity_id1 = uuid4()
        event = Example.Created(
            originator_id=entity_id1, originator_topic=get_topic(Example), a=1, b=2
        )

        # Check constructor keyword args lead to read-only attributes.
        self.assertEqual(1, event.a)
        self.assertEqual(2, event.b)
        self.assertRaises(AttributeError, getattr, event, "c")
        self.assertRaises(AttributeError, setattr, event, "c", 3)

        # Check domain event has auto-generated timestamp.
        self.assertIsInstance(event.timestamp, Decimal)

        # Check timestamp value can be given to domain events.
        event1 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=1,
            b=2,
            timestamp=3,
        )
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
        publish([event])
        predicate.assert_called_once_with([event])
        handler.assert_called_once_with([event])

        # When predicate is True, after unsubscribing, handler should NOT be called
        # again.
        unsubscribe(handler=handler, predicate=predicate)
        publish([event])
        predicate.assert_called_once_with([event])
        handler.assert_called_once_with([event])

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

        # When predicate is False, handler should NOT be called.
        predicate = lambda x: False
        handler = mock.Mock()
        subscribe(handler=handler, predicate=predicate)
        publish([event])
        self.assertEqual(0, handler.call_count)

        # Unsubscribe.
        unsubscribe(handler=handler, predicate=predicate)

        # Check we can assert there are no event handlers subscribed.
        assert_event_handlers_empty()

    def test_hash(self):
        entity_id1 = uuid4()
        event1 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=1,
            b=2,
            timestamp=3,
        )
        event2 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=1,
            b=2,
            timestamp=3,
        )
        self.assertEqual(hash(event1), hash(event2))

    def test_equality_comparison(self):
        entity_id1 = uuid4()
        event1 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=1,
            b=2,
            timestamp=3,
        )
        event2 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=1,
            b=2,
            timestamp=3,
        )
        event3 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=3,
            b=2,
            timestamp=3,
        )
        self.assertEqual(event1, event2)
        self.assertNotEqual(event1, event3)
        self.assertNotEqual(event2, event3)
        self.assertNotEqual(event2, None)

    def test_repr(self):
        entity_id1 = UUID("c7383095-85a3-4c49-ae32-9c9957ac8579")
        event1 = Example.Created(
            originator_id=entity_id1,
            originator_topic=get_topic(Example),
            a=1,
            b=2,
            timestamp=3,
        )
        self.maxDiff = None
        self.assertEqual(
            (
                "Example.Created("
                "__event_hash__='dbd0d45ed797de4f9a5d574ec4e3da3df74e67641bd7632dd05ffa28a5876391', "
                "__event_hash_method_name__='__hash_object_v2__', "
                "__event_topic__='eventsourcing.example.domainmodel#Example.Created', "
                "a=1, b=2, "
                "originator_id={}, "
                "originator_topic='eventsourcing.example.domainmodel#Example', "
                "originator_version=0, timestamp=3)"
            ).format(repr(entity_id1)),
            repr(event1),
        )

    def test_topic_resolution_error(self):
        # Check topic resolution error is raised, if the module path is
        # broken, and if the class name is broken.
        resolve_topic("eventsourcing.domain.model.events#DomainEvent")
        with self.assertRaises(TopicResolutionError):
            resolve_topic("eventsourcing.domain.model.broken#DomainEvent")
        with self.assertRaises(TopicResolutionError):
            resolve_topic("eventsourcing.domain.model.events#Broken")


class TestEventWithHash(TestCase):
    def test_event_hash_versioning(self):
        event = EventWithHash(a=1, b=1)
        self.assertTrue("__event_hash__", event.__dict__)
        self.assertIn("__event_hash_method_name__", event.__dict__)
        self.assertEqual(
            event.__dict__["__event_hash_method_name__"], "__hash_object_v2__"
        )
        event.__check_hash__()

        # Redo hashing, as a version 1, but with v2 __event_hash_method_name__.
        event.__dict__.pop("__event_hash__")
        event.__dict__["__event_hash__"] = event.__hash_object_v1__(event.__dict__)
        with self.assertRaises(EventHashError):
            event.__check_hash__()

        # Redo hashing, as a version 1, and without __event_hash_method_name__.
        event.__dict__.pop("__event_hash_method_name__")
        event.__dict__.pop("__event_hash__")
        event.__dict__["__event_hash__"] = event.__hash_object_v1__(event.__dict__)
        event.__check_hash__()

        # Redo hashing, as a version 2, but without __event_hash_method_name__.
        #
        # This should fail because it will fail to find an __event_hash_method_name__
        # and so it will assume the state wasn't recorded with that, and so use v1 by
        # default, which won't match with the v2 hash created below.
        event.__dict__.pop("__event_hash__")
        event.__dict__["__event_hash__"] = event.__hash_object_v2__(event.__dict__)
        with self.assertRaises(EventHashError):
            event.__check_hash__()
