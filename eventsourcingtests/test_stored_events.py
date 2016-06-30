import datetime
import unittest
import uuid
from uuid import uuid1

import six

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.domain.model.example import Example
from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.infrastructure.stored_events.base import SimpleStoredEventIterator, ThreadedStoredEventIterator, \
    StoredEventRepository
from eventsourcing.infrastructure.stored_events.transcoders import serialize_domain_event, deserialize_domain_event, \
    resolve_domain_topic, StoredEvent, ObjectJSONDecoder, ObjectJSONEncoder
from eventsourcing.utils.time import utc_timezone


class TestStoredEvent(unittest.TestCase):

    def test_serialize_domain_event(self):
        datetime_now = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429)
        datetime_now_tzaware = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429, tzinfo=utc_timezone)
        date_now = datetime.date(2015, 9, 8)
        event1 = DomainEvent(a=1, b=2, c=datetime_now, d=datetime_now_tzaware, e=date_now, entity_version=0, entity_id='entity1', domain_event_id=3)
        stored_event = serialize_domain_event(event1, json_encoder_cls=ObjectJSONEncoder)
        self.assertEqual('DomainEvent::entity1', stored_event.stored_entity_id)
        self.assertEqual('eventsourcing.domain.model.events#DomainEvent', stored_event.event_topic)
        self.assertEqual('{"a":1,"b":2,"c":{"ISO8601_datetime":"2015-09-08T16:20:50.577429"},"d":{"ISO8601_datetime":"2015-09-08T16:20:50.577429+0000"},"domain_event_id":3,"e":{"ISO8601_date":"2015-09-08"},"entity_id":"entity1","entity_version":0}',
                         stored_event.event_attrs)

    def test_serialize_domain_event_with_numpy_array(self):
        try:
            import numpy
        except ImportError:
            numpy = None

        if numpy is not None:
            event1 = DomainEvent(a=numpy.array([10.123456]), entity_version=0, entity_id='entity1', domain_event_id=3)

            stored_event = serialize_domain_event(event1, json_encoder_cls=ObjectJSONEncoder)
            self.assertEqual('eventsourcing.domain.model.events#DomainEvent', stored_event.event_topic)
            self.assertEqual('{"a":{"__ndarray__":"\\"\\\\u0093NUMPY\\\\u0001\\\\u0000F\\\\u0000{\'descr\': \'<f8\', \'fortran_order\': False, \'shape\': (1,), }            \\\\nm\\\\u00fd\\\\u00f4\\\\u009f5?$@\\""},"domain_event_id":3,"entity_id":"entity1","entity_version":0}',
                             stored_event.event_attrs)
        else:
            self.skipTest("Numpy not installed")

    def test_recreate_domain_event(self):
        stored_event = StoredEvent(event_id='1',
                                   stored_entity_id='entity1',
                                   event_topic='eventsourcing.domain.model.events#DomainEvent',
                                   event_attrs='{"a":1,"b":2,"c":{"ISO8601_datetime":"2015-09-08T16:20:50.577429"},"d":{"ISO8601_datetime":"2015-09-08T16:20:50.577429+0000"},"domain_event_id":3,"e":{"ISO8601_date":"2015-09-08"},"entity_id":"entity1","entity_version":0}')
        domain_event = deserialize_domain_event(stored_event, json_decoder_cls=ObjectJSONDecoder)
        self.assertIsInstance(domain_event, DomainEvent)
        self.assertEqual('entity1', domain_event.entity_id)
        self.assertEqual(1, domain_event.a)
        self.assertEqual(2, domain_event.b)
        datetime_now_timezoneaware = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429, tzinfo=utc_timezone)
        # self.assertEqual(datetime_now, domain_event.c)
        self.assertEqual(datetime_now_timezoneaware, domain_event.d)
        date_now = datetime.date(2015, 9, 8)
        self.assertEqual(date_now, domain_event.e)
        self.assertEqual(3, domain_event.domain_event_id)

        # Check the TypeError is raised.
        stored_event = StoredEvent(event_id='1',
                                   stored_entity_id='entity1',
                                   event_topic='os#path',
                                   event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":3}')
        self.assertRaises(TypeError, deserialize_domain_event, stored_event, json_decoder_cls=ObjectJSONDecoder)

    def test_resolve_event_topic(self):
        example_topic = 'eventsourcing.domain.model.example#Example.Created'
        actual = resolve_domain_topic(example_topic)
        self.assertEqual(Example.Created, actual)
        example_topic = 'xxxxxxxxxxxxx#Example.Event'
        self.assertRaises(TopicResolutionError, resolve_domain_topic, example_topic)
        example_topic = 'eventsourcing.domain.model.example#Xxxxxxxx.Xxxxxxxx'
        self.assertRaises(TopicResolutionError, resolve_domain_topic, example_topic)


class AbstractTestCase(unittest.TestCase):

    def setUp(self):
        """
        Returns None if test case class ends with 'TestCase', which means the test case isn't included in the suite.
        """
        if type(self).__name__.endswith('TestCase'):
            self.skipTest('Abstract test ignored.\n')
        else:
            super(AbstractTestCase, self).setUp()


class AbstractStoredEventRepositoryTestCase(AbstractTestCase):

    @property
    def stored_event_repo(self):
        """
        :rtype: StoredEventRepository
        """
        raise NotImplementedError


class BasicStoredEventRepositoryTestCase(AbstractStoredEventRepositoryTestCase):

    def test_stored_event_repo(self):
        stored_entity_id = 'Entity::entity1'

        # Check the repo returns None for calls to get_most_recent_event() when there aren't any events.
        self.assertIsNone(self.stored_event_repo.get_most_recent_event(stored_entity_id))

        # Store an event for 'entity1'.
        stored_event1 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.domain.model.example#Example.Created',
                                    event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":3}')
        self.stored_event_repo.append(stored_event1)

        # Store another event for 'entity1'.
        stored_event2 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.domain.model.example#Example.Created',
                                    event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":4}')
        self.stored_event_repo.append(stored_event2)

        # Get all events for 'entity1'.
        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.

        num_fixture_events = 2

        self.assertEqual(num_fixture_events, len(retrieved_events))
        # - check the first event
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        # - check the second event
        self.assertIsInstance(retrieved_events[1], StoredEvent)
        self.assertEqual(stored_event2.event_topic, retrieved_events[1].event_topic)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[1].event_attrs)

        # Get with limit (depends on query order).
        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, limit=1, query_ascending=True)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        # - check the first retrieved event is the first event that was stored
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)

        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, limit=1, query_ascending=False)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        # - check the first retrieved event is the last event that was stored
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event2.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[0].event_attrs)

        # Get the most recent event for 'entity1'.
        most_recent_event = self.stored_event_repo.get_most_recent_event(stored_entity_id)
        self.assertIsInstance(most_recent_event, StoredEvent)
        self.assertEqual(most_recent_event.event_id, stored_event2.event_id)

        # Get all events for 'entity1' since the first event's timestamp.
        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, after=stored_event1.event_id)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        self.assertEqual(1, len(list(retrieved_events)))
        # - check the last event is first
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event2.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[0].event_attrs)

        # Store lots of events, and check the latest events can be retrieved quickly.
        stored_events = []
        num_extra_events = 127
        for page_count in six.moves.range(num_extra_events):
            stored_event_i = StoredEvent(event_id=uuid.uuid1().hex,
                                         stored_entity_id=stored_entity_id,
                                         event_topic='eventsourcing.domain.model.example#Example.Created',
                                         event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":%s}' % (page_count+10))
            stored_events.append(stored_event_i)
            self.stored_event_repo.append(stored_event_i)

        last_snapshot_event = stored_events[-20]

        # start_time = datetime.datetime.now()
        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, after=last_snapshot_event.event_id)
        retrieved_events = list(retrieved_events)
        # page_duration = (datetime.datetime.now() - start_time).total_seconds()
        # self.assertLess(page_duration, 0.05)
        # print("Duration: {}".format(page_duration))

        self.assertEqual(len(retrieved_events), 19)
        self.assertIsInstance(retrieved_events[-1], StoredEvent)
        self.assertEqual(stored_events[-19].event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_events[-19].event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_events[-1].event_topic, retrieved_events[-1].event_topic)
        self.assertEqual(stored_events[-1].event_attrs, retrieved_events[-1].event_attrs)

        # Check the first events can be retrieved easily.
        start_time = datetime.datetime.now()
        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, limit=20, query_ascending=True)
        retrieved_events = list(retrieved_events)
        page_duration = (datetime.datetime.now() - start_time).total_seconds()
        # print("Duration: {}".format(page_duration))
        # self.assertLess(page_duration, 0.05)
        self.assertEqual(len(retrieved_events), 20)
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)

        # Check the next page of events can be retrieved easily.
        start_time = datetime.datetime.now()
        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, after=retrieved_events[-1].event_id,
                                                               limit=20, query_ascending=True)
        retrieved_events = list(retrieved_events)
        page_duration = (datetime.datetime.now() - start_time).total_seconds()
        # self.assertLess(page_duration, 0.05)
        # print("Duration: {}".format(page_duration))

        self.assertEqual(len(retrieved_events), 20)
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_events[18].event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_events[18].event_attrs, retrieved_events[0].event_attrs)


class IteratorTestCase(AbstractStoredEventRepositoryTestCase):

    @property
    def stored_entity_id(self):
        return 'Entity::1'

    @property
    def num_events(self):
        return 12

    @property
    def iterator_cls(self):
        """
        Returns iterator class.
        """
        raise NotImplementedError

    def create_iterator(self, is_ascending, page_size):
        return self.iterator_cls(
            repo=self.stored_event_repo,
            stored_entity_id=self.stored_entity_id,
            page_size=page_size,
            is_ascending=is_ascending,
        )

    def setup_stored_events(self):
        self.stored_events = []
        self.number_of_stored_events = 12
        for page_number in six.moves.range(self.number_of_stored_events):
            stored_event = StoredEvent(
                event_id=uuid.uuid1().hex,
                stored_entity_id=self.stored_entity_id,
                event_topic='eventsourcing.domain.model.example#Example.Created',
                event_attrs='{"a":%s,"b":2,"stored_entity_id":"%s","timestamp":%s}' % (
                    page_number, self.stored_entity_id, uuid1().hex
                )
            )
            self.stored_events.append(stored_event)
            self.stored_event_repo.append(stored_event)

    def test(self):
        self.setup_stored_events()

        assert isinstance(self.stored_event_repo, StoredEventRepository)
        stored_events = self.stored_event_repo.get_entity_events(stored_entity_id=self.stored_entity_id)
        stored_events = list(stored_events)
        self.assertEqual(len(stored_events), self.num_events)

        # Check can get all events.
        page_size = 5

        # Iterate ascending.
        is_ascending = True
        expect_at_start = self.stored_events[0].event_attrs
        expect_at_end = self.stored_events[-1].event_attrs
        self.assert_iterator_yields_events(is_ascending, expect_at_start, expect_at_end, page_size)

        # Iterate descending.
        is_ascending = False
        expect_at_start = self.stored_events[-1].event_attrs
        expect_at_end = self.stored_events[0].event_attrs
        self.assert_iterator_yields_events(is_ascending, expect_at_start, expect_at_end, page_size)

    def assert_iterator_yields_events(self, is_ascending, expect_at_start, expect_at_end, page_size):
        iterator = self.create_iterator(is_ascending, page_size)
        retrieved_events = list(iterator)
        self.assertEqual(len(retrieved_events), len(self.stored_events))
        self.assertGreater(len(retrieved_events), page_size)
        self.assertEqual(iterator.page_counter, 3)
        self.assertEqual(iterator.all_event_counter, self.num_events)
        self.assertEqual(expect_at_start, retrieved_events[0].event_attrs)
        self.assertEqual(expect_at_end, retrieved_events[-1].event_attrs)


class SimpleStoredEventIteratorTestCase(IteratorTestCase):

    @property
    def iterator_cls(self):
        return SimpleStoredEventIterator


class ThreadedStoredEventIteratorTestCase(IteratorTestCase):

    @property
    def iterator_cls(self):
        return ThreadedStoredEventIterator
