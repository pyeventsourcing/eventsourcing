import unittest
import datetime
import uuid
from eventsourcing.domain.model.events import DomainEvent

from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.infrastructure.stored_events.base import StoredEvent, InMemoryStoredEventRepository, \
    serialize_domain_event, recreate_domain_event, resolve_event_topic
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import CassandraStoredEventRepository, \
    setup_cassandra_connection, shutdown_cassandra_connection, get_cassandra_setup_params, CqlStoredEvent
from eventsourcing.infrastructure.stored_events.rdbms import SQLAlchemyStoredEventRepository, \
    get_scoped_session_facade
from eventsourcing.domain.model.example import Example
from eventsourcing.utils.time import utc_now, utc_timezone


class TestStoredEvent(unittest.TestCase):

    def test_serialize_domain_event(self):
        datetime_now = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429)
        datetime_now_tzaware = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429, tzinfo=utc_timezone)
        date_now = datetime.date(2015, 9, 8)
        event1 = DomainEvent(a=1, b=2, c=datetime_now, d=datetime_now_tzaware, e=date_now, entity_version=0, entity_id='entity1', timestamp=3)
        stored_event = serialize_domain_event(event1)
        self.assertEqual('DomainEvent::entity1', stored_event.stored_entity_id)
        self.assertEqual('eventsourcing.domain.model.events#DomainEvent', stored_event.event_topic)
        self.assertEqual('{"a":1,"b":2,"c":{"ISO8601_datetime":"2015-09-08T16:20:50.577429"},"d":{"ISO8601_datetime":"2015-09-08T16:20:50.577429+0000"},"e":{"ISO8601_date":"2015-09-08"},"entity_id":"entity1","entity_version":0,"timestamp":3}',
                         stored_event.event_attrs)

    def test_recreate_domain_event(self):
        stored_event = StoredEvent(event_id='1',
                                   stored_entity_id='entity1',
                                   event_topic='eventsourcing.domain.model.events#DomainEvent',
                                   event_attrs='{"a":1,"b":2,"c":{"ISO8601_datetime":"2015-09-08T16:20:50.577429"},"d":{"ISO8601_datetime":"2015-09-08T16:20:50.577429+0000"},"e":{"ISO8601_date":"2015-09-08"},"entity_id":"entity1","entity_version":0,"timestamp":3}')
        domain_event = recreate_domain_event(stored_event)
        self.assertIsInstance(domain_event, DomainEvent)
        self.assertEqual('entity1', domain_event.entity_id)
        self.assertEqual(1, domain_event.a)
        self.assertEqual(2, domain_event.b)
        datetime_now = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429)
        datetime_now_tzaware = datetime.datetime(2015, 9, 8, 16, 20, 50, 577429, tzinfo=utc_timezone)
        # self.assertEqual(datetime_now, domain_event.c)
        self.assertEqual(datetime_now_tzaware, domain_event.d)
        date_now = datetime.date(2015, 9, 8)
        self.assertEqual(date_now, domain_event.e)
        self.assertEqual(3, domain_event.timestamp)

        # Check the TypeError is raised.
        stored_event = StoredEvent(event_id='1',
                                   stored_entity_id='entity1',
                                   event_topic='os#path',
                                   event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        self.assertRaises(TypeError, recreate_domain_event, stored_event)

    def test_resolve_event_topic(self):
        example_topic = 'eventsourcing.domain.model.example#Example.Created'
        actual = resolve_event_topic(example_topic)
        self.assertEqual(Example.Created, actual)
        example_topic = 'xxxxxxxxxxxxx#Example.Event'
        self.assertRaises(TopicResolutionError, resolve_event_topic, example_topic)
        example_topic = 'eventsourcing.domain.model.example#Xxxxxxxx.Xxxxxxxx'
        self.assertRaises(TopicResolutionError, resolve_event_topic, example_topic)


class StoredEventRepositoryTestCase(unittest.TestCase):

    def assertStoredEventRepositoryImplementation(self, stored_event_repo):
        # Store an event for 'entity1'.
        stored_event1 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id='entity1',
                                    event_topic='eventsourcing.domain.model.example#Example.Created',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        stored_event_repo.append(stored_event1)

        # Check the repo contains the event.
        self.assertIn(stored_event1.event_id, stored_event_repo)  # __contains__
        self.assertIsInstance(stored_event_repo[stored_event1.event_id], StoredEvent)  # __getitem__
        self.assertIsInstance(repr(stored_event_repo[stored_event1.event_id]), str)  # __getitem__

        # Store another event for 'entity1'.
        stored_event2 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id='entity1',
                                    event_topic='eventsourcing.domain.model.example#Example.Created',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":4}')
        stored_event_repo.append(stored_event2)

        # Get all events for 'entity1'.
        events = stored_event_repo.get_entity_events('entity1')
        events = list(events)  # Make sequence from the iterator.
        self.assertEqual(2, len(list(events)))
        # - check the first event
        self.assertIsInstance(events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, events[0].event_attrs)
        # - check the second event
        self.assertIsInstance(events[1], StoredEvent)
        self.assertEqual(stored_event2.event_topic, events[1].event_topic)
        self.assertEqual(stored_event2.event_attrs, events[1].event_attrs)

        # Get all events for the topic.
        events = stored_event_repo.get_topic_events('eventsourcing.domain.model.example#Example.Created')
        events = list(events)
        self.assertEqual(2, len(events))
        # - check the first event
        self.assertIsInstance(events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, events[0].event_attrs)
        # - check the second event
        self.assertIsInstance(events[1], StoredEvent)
        self.assertEqual(stored_event2.event_topic, events[1].event_topic)
        self.assertEqual(stored_event2.event_attrs, events[1].event_attrs)


class TestInMemoryStoredEventRepository(StoredEventRepositoryTestCase):

    def test(self):
        self.assertStoredEventRepositoryImplementation(InMemoryStoredEventRepository())


class TestSQLAlchemyStoredEventRepository(StoredEventRepositoryTestCase):

    def test(self):
        stored_event_repo = SQLAlchemyStoredEventRepository(get_scoped_session_facade('sqlite:///:memory:'))
        self.assertStoredEventRepositoryImplementation(stored_event_repo)


class TestCassandraStoredEventRepository(StoredEventRepositoryTestCase):

    def setUp(self):
        super(TestCassandraStoredEventRepository, self).setUp()
        setup_cassandra_connection(*get_cassandra_setup_params(default_keyspace='eventsourcingtests2'))

    def tearDown(self):
        for cql_stored_event in CqlStoredEvent.objects.all():
            cql_stored_event.delete()
        shutdown_cassandra_connection()
        super(TestCassandraStoredEventRepository, self).tearDown()

    def test(self):
        stored_event_repo = CassandraStoredEventRepository()
        self.assertStoredEventRepositoryImplementation(stored_event_repo)
