import unittest
from eventsourcing.exceptions import TopicResolutionError
from eventsourcing.infrastructure.stored_events import serialize_domain_event, recreate_domain_event, \
    resolve_event_topic, StoredEvent, InMemoryStoredEventRepository
from eventsourcing.infrastructure.stored_events_sqlalchemy import SQLAlchemyStoredEventRepository, get_scoped_session
from eventsourcing.domain.model.example import Example


class TestStoredEvent(unittest.TestCase):

    def test_serialize_domain_event(self):
        event1 = Example.Event(a=1, b=2, entity_id='entity1', timestamp=3)
        stored_event = serialize_domain_event(event1)
        self.assertEqual('entity1', stored_event.entity_id)
        self.assertEqual('eventsourcing.domain.model.example#Example.Event', stored_event.event_topic)
        self.assertEqual('{"a":1,"b":2,"entity_id":"entity1","timestamp":3}', stored_event.event_attrs)

    def test_recreate_domain_event(self):
        stored_event = StoredEvent(event_id='1',
                                   entity_id='entity1',
                                   event_topic='eventsourcing.domain.model.example#Example.Event',
                                   event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        domain_event = recreate_domain_event(stored_event)
        self.assertIsInstance(domain_event, Example.Event)
        self.assertEqual('entity1', domain_event.entity_id)
        self.assertEqual(1, domain_event.a)
        self.assertEqual(2, domain_event.b)
        self.assertEqual(3, domain_event.timestamp)

    def test_resolve_event_topic(self):
        example_topic = 'eventsourcing.domain.model.example#Example.Event'
        actual = resolve_event_topic(example_topic)
        self.assertEqual(Example.Event, actual)
        example_topic = 'xxxxxxxxxxxxx#Example.Event'
        self.assertRaises(TopicResolutionError, resolve_event_topic, example_topic)
        example_topic = 'eventsourcing.domain.model.example#Xxxxxxxx.Xxxxxxxx'
        self.assertRaises(TopicResolutionError, resolve_event_topic, example_topic)


class StoredEventRepositoryTestCase(unittest.TestCase):

    def assertStoredEventRepositoryImplementation(self, stored_event_repo):
        # Store an event for 'entity1'.
        stored_event1 = StoredEvent(event_id='1',
                                    entity_id='entity1',
                                    event_topic='eventsourcing.domain.model.example#Example.Event',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":3}')
        stored_event_repo.append(stored_event1)

        # Check the repo contains the event.
        self.assertIn(stored_event1.event_id, stored_event_repo)  # __contains__
        self.assertIsInstance(stored_event_repo[stored_event1.event_id], StoredEvent)  # __getitem__

        # Store another event for 'entity1'.
        stored_event2 = StoredEvent(event_id='2',
                                    entity_id='entity1',
                                    event_topic='eventsourcing.domain.model.example#Example.Event',
                                    event_attrs='{"a":1,"b":2,"entity_id":"entity1","timestamp":4}')
        stored_event_repo.append(stored_event2)

        # Get all events for 'entity1'.
        events = stored_event_repo.get_entity_events('entity1')
        self.assertEqual(2, len(events))
        # - check the first event
        self.assertIsInstance(events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, events[0].event_attrs)
        # - check the second event
        self.assertIsInstance(events[1], StoredEvent)
        self.assertEqual(stored_event2.event_topic, events[1].event_topic)
        self.assertEqual(stored_event2.event_attrs, events[1].event_attrs)

        # Get all events for the topic.
        events = stored_event_repo.get_topic_events('eventsourcing.domain.model.example#Example.Event')
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
        stored_event_repo = SQLAlchemyStoredEventRepository(get_scoped_session())
        self.assertStoredEventRepositoryImplementation(stored_event_repo)
