import datetime
from unittest.case import TestCase

from six import with_metaclass

from eventsourcing.domain.model.events import DomainEvent, QualnameABCMeta, topic_from_domain_class
from eventsourcing.example.domain_model import Example
from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.infrastructure.transcoding import JSONStoredEventTranscoder, StoredEvent, resolve_domain_topic
from eventsourcing.utils.time import utc_timezone


class TestStoredEvent(TestCase):

    def test_serialize_domain_event_with_uuid1(self):
        datetime_now = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429)
        datetime_now_tzaware = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429, tzinfo=utc_timezone)
        date_now = datetime.date(2015, 9, 8)
        event1 = DomainEvent(a=1, b=2, c=datetime_now, d=datetime_now_tzaware, e=date_now, entity_version=0,
                             entity_id='entity1', domain_event_id=3)
        stored_event = JSONStoredEventTranscoder().serialize(event1)
        self.assertEqual('DomainEvent::entity1', stored_event.stored_entity_id)
        self.assertEqual('eventsourcing.domain.model.events#DomainEvent', stored_event.event_topic)
        self.assertEqual('{"a":1,"b":2,"c":{"ISO8601_datetime":"2015-09-08T16:20:50.577429"},"d":{"ISO8601_datetime":'
                         '"2015-09-08T16:20:50.577429+0000"},"e":{"ISO8601_date":"2015-09-08"},"entity_id":"entity1",'
                         '"entity_version":0}',
                         stored_event.event_attrs)

    def test_serialize_domain_event_with_uuid4(self):
        datetime_now = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429)
        datetime_now_tzaware = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429, tzinfo=utc_timezone)
        date_now = datetime.date(2015, 9, 8)
        event1 = DomainEvent(a=1, b=2, c=datetime_now, d=datetime_now_tzaware, e=date_now, entity_version=0,
                             entity_id='entity1', domain_event_id=3)
        stored_event = JSONStoredEventTranscoder().serialize(event1)
        self.assertEqual('DomainEvent::entity1', stored_event.stored_entity_id)
        self.assertEqual('eventsourcing.domain.model.events#DomainEvent', stored_event.event_topic)
        self.assertEqual('{"a":1,"b":2,"c":{"ISO8601_datetime":"2015-09-08T16:20:50.577429"},"d":{"ISO8601_datetime":'
                         '"2015-09-08T16:20:50.577429+0000"},"e":{"ISO8601_date":"2015-09-08"},"entity_id":"entity1",'
                         '"entity_version":0}',
                         stored_event.event_attrs)

    def test_serialize_domain_event_with_numpy_array(self):
        try:
            import numpy
        except ImportError:
            numpy = None

        if numpy is not None:
            event1 = DomainEvent(a=numpy.array([10.123456]), entity_version=0, entity_id='entity1', domain_event_id=3)

            stored_event = JSONStoredEventTranscoder().serialize(event1)
            self.assertEqual('eventsourcing.domain.model.events#DomainEvent', stored_event.event_topic)
            self.assertEqual('{"a":{"__ndarray__":"\\"\\\\u0093NUMPY\\\\u0001\\\\u0000F\\\\u0000{\'descr\': \'<f8\', '
                             '\'fortran_order\': False, \'shape\': (1,), }            \\\\nm\\\\u00fd\\\\u00f4\\\\u00'
                             '9f5?$@\\""},"entity_id":"entity1","entity_version":0}',
                             stored_event.event_attrs)
        else:
            self.skipTest("Skipped test because numpy is not installed")

    def test_recreate_domain_event(self):
        stored_event = StoredEvent(event_id='1',
                                   stored_entity_id='entity1',
                                   event_topic='eventsourcing.domain.model.events#DomainEvent',
                                   event_attrs=('{"a":1,"b":2,"c":{"ISO8601_datetime":"2015-09-08T16:20:50.577429"},'
                                                '"d":{"ISO8601_datetime":"2015-09-08T16:20:50.577429+0000"},"e":{"I'
                                                'SO8601_date":"2015-09-08"},"entity_id":"entity1"}'))
        domain_event = JSONStoredEventTranscoder().deserialize(stored_event)

        self.assertIsInstance(domain_event, DomainEvent)
        self.assertEqual('entity1', domain_event.entity_id)
        self.assertEqual(1, domain_event.a)
        self.assertEqual(2, domain_event.b)
        datetime_now_timezoneaware = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429, tzinfo=utc_timezone)
        # self.assertEqual(datetime_now, domain_event.c)
        self.assertEqual(datetime_now_timezoneaware, domain_event.d)
        date_now = datetime.date(2015, 9, 8)
        self.assertEqual(date_now, domain_event.e)
        self.assertEqual('1', domain_event.domain_event_id)

        # Check the TypeError is raised.
        stored_event = StoredEvent(event_id='1',
                                   stored_entity_id='entity1',
                                   event_topic=topic_from_domain_class(NotADomainEvent),
                                   event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":3}')
        with self.assertRaises(ValueError):
            JSONStoredEventTranscoder().deserialize(stored_event)

    def test_resolve_event_topic(self):
        example_topic = 'eventsourcing.example.domain_model#Example.Created'
        actual = resolve_domain_topic(example_topic)
        self.assertEqual(Example.Created, actual)
        example_topic = 'xxxxxxxxxxxxx#Example.Event'
        self.assertRaises(TopicResolutionError, resolve_domain_topic, example_topic)
        example_topic = 'eventsourcing.example.domain_model#Xxxxxxxx.Xxxxxxxx'
        self.assertRaises(TopicResolutionError, resolve_domain_topic, example_topic)


class NotADomainEvent(with_metaclass(QualnameABCMeta)):
    pass
