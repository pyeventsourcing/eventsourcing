import datetime
import unittest
import uuid

import six

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.domain.model.example import Example
from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.infrastructure.stored_events.base import SimpleStoredEventIterator
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
                                   event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        self.assertRaises(TypeError, deserialize_domain_event, stored_event, json_decoder_cls=ObjectJSONDecoder)

    def test_resolve_event_topic(self):
        example_topic = 'eventsourcing.domain.model.example#Example.Created'
        actual = resolve_domain_topic(example_topic)
        self.assertEqual(Example.Created, actual)
        example_topic = 'xxxxxxxxxxxxx#Example.Event'
        self.assertRaises(TopicResolutionError, resolve_domain_topic, example_topic)
        example_topic = 'eventsourcing.domain.model.example#Xxxxxxxx.Xxxxxxxx'
        self.assertRaises(TopicResolutionError, resolve_domain_topic, example_topic)


class StoredEventRepositoryTestCase(unittest.TestCase):

    def checkStoredEventRepository(self, stored_event_repo):
        stored_entity_id = 'Entity::entity1'

        # Check the repo returns None for calls to get_most_recent_event() when there aren't any events.
        self.assertIsNone(stored_event_repo.get_most_recent_event(stored_entity_id))

        # # Check the repo doesn't contain an event.
        # pk = (stored_entity_id, domain_event_id.uuid1())
        # self.assertNotIn(pk, stored_event_repo)  # __contains__
        # self.assertRaises(KeyError, stored_event_repo.__getitem__, pk)  # __getitem__

        # Store an event for 'entity1'.
        stored_event1 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.domain.model.example#Example.Created',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        stored_event_repo.append(stored_event1)

        # # Check the repo contains the event.
        # pk = (stored_entity_id, stored_event1.event_id)
        # self.assertIn(pk, stored_event_repo)  # __contains__
        # self.assertIsInstance(stored_event_repo[pk], StoredEvent)  # __getitem__
        # self.assertIsInstance(repr(stored_event_repo[pk]), str)  # __getitem__

        # Store another event for 'entity1'.
        stored_event2 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.domain.model.example#Example.Created',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":4}')
        stored_event_repo.append(stored_event2)

        # Get all events for 'entity1'.
        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id)
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
        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id, query_asc=True, limit=1)
        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id, query_asc=True, limit=1)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        # - check the first retrieved event is the first event that was stored
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)

        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id, query_asc=False, limit=1)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        # - check the first retrieved event is the last event that was stored
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event2.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[0].event_attrs)

        # Get the most recent event for 'entity1'.
        most_recent_event = stored_event_repo.get_most_recent_event(stored_entity_id)
        self.assertIsInstance(most_recent_event, StoredEvent)
        self.assertEqual(most_recent_event.event_id, stored_event2.event_id)

        # Get all events for 'entity1' since the first event's timestamp.
        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id, after=stored_event1.event_id)
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
                                         event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":%s}' % (page_count+10))
            stored_events.append(stored_event_i)
            stored_event_repo.append(stored_event_i)

        last_snapshot_event = stored_events[-20]

        # start_time = datetime.datetime.now()
        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id, after=last_snapshot_event.event_id)
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
        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id, query_asc=True, limit=20)
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
        retrieved_events = stored_event_repo.get_entity_events(stored_entity_id,
                                                               after=retrieved_events[-1].event_id,
                                                               limit=20,
                                                               query_asc=True)
        retrieved_events = list(retrieved_events)
        page_duration = (datetime.datetime.now() - start_time).total_seconds()
        # self.assertLess(page_duration, 0.05)
        # print("Duration: {}".format(page_duration))

        self.assertEqual(len(retrieved_events), 20)
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_events[18].event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_events[18].event_attrs, retrieved_events[0].event_attrs)

        # Check the stored event iterator can get all the events.
        # Todo: Move this test of the SimpleStoredEventIterator to a separate test case?
        # Todo: Write a test case for ThreadedStoredEventIterator.
        # start_time = datetime.datetime.now()
        page_size = 50
        iterator = SimpleStoredEventIterator(stored_event_repo, stored_entity_id, page_size=page_size)
        retrieved_events = list(iterator)
        self.assertGreater(len(retrieved_events), page_size)

        self.assertEqual(iterator.page_counter, 3)
        self.assertEqual(iterator.all_event_counter, num_fixture_events + num_extra_events)

        # Check the first and last stored event.
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_events[-1].event_attrs, retrieved_events[-1].event_attrs)

        # duration = (datetime.datetime.now() - start_time).total_seconds()

        # print("Total duration: {}".format(duration))
        # average_item_duration = duration / len(retrieved_events)

        # print("Average item duration: {}".format(average_item_duration))
        # print("Average item rate: {}".format(1.0 / average_item_duration))
        # self.assertLess(average_item_duration, 0.0005)
