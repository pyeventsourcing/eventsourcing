import datetime
import json
import uuid
from abc import abstractmethod, abstractproperty
from uuid import uuid1

import six

from eventsourcing.application.policies import PersistenceSubscriber
from eventsourcing.domain.model.events import IntegerSequencedEvent, topic_from_domain_class
from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError, EntityVersionNotFound, \
    IntegerSequenceError
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository, EventStore, \
    SimpleStoredEventIterator
from eventsourcing.infrastructure.storedevents.threaded_iterator import ThreadedStoredEventIterator
from eventsourcing.infrastructure.transcoding import StoredEvent, StoredIntegerSequencedEvent
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase


class AbstractStoredEventRepositoryTestCase(AbstractDatastoreTestCase):
    def __init__(self, *args, **kwargs):
        super(AbstractStoredEventRepositoryTestCase, self).__init__(*args, **kwargs)
        self._stored_event_repo = None

    def setUp(self):
        super(AbstractStoredEventRepositoryTestCase, self).setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            self.datastore.setup_tables()

    def tearDown(self):
        self._stored_event_repo = None
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.drop_connection()
        super(AbstractStoredEventRepositoryTestCase, self).tearDown()

    @property
    def stored_event_repo(self):
        """
        :rtype: eventsourcing.infrastructure.eventstore.AbstractStoredEventRepository
        """
        if self._stored_event_repo is None:
            self._stored_event_repo = self.construct_stored_event_repo()
        return self._stored_event_repo

    @abstractmethod
    def construct_stored_event_repo(self):
        """
        :rtype: eventsourcing.infrastructure.eventstore.AbstractStoredEventRepository
        """

class ExampleIntegerSequencedEvent1(IntegerSequencedEvent):
    pass


class ExampleIntegerSequencedEvent2(IntegerSequencedEvent):
    pass


EXAMPLE_EVENT_TOPIC1 = topic_from_domain_class(ExampleIntegerSequencedEvent1)
EXAMPLE_EVENT_TOPIC2 = topic_from_domain_class(ExampleIntegerSequencedEvent2)


class IntegerSequencedEventRepositoryTestCase(AbstractStoredEventRepositoryTestCase):

    def test_event_repo(self):
        sequence_id = uuid.uuid1().hex

        # Check repo returns None when there aren't any events.
        self.assertEqual(self.stored_event_repo.get_integer_sequenced_events(sequence_id), [])

        # Append an event.
        state1 = json.dumps({'name': 'value1'})
        stored_event1 = StoredIntegerSequencedEvent(
            sequence_id=sequence_id,
            position=0,
            topic=EXAMPLE_EVENT_TOPIC1,
            state=state1,
        )
        self.stored_event_repo.append_integer_sequenced_event(stored_event1)

        # Check repo returns the event.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id)
        self.assertIsInstance(retrieved_events[0], StoredIntegerSequencedEvent)
        self.assertEqual(retrieved_events[0].sequence_id, stored_event1.sequence_id)
        self.assertEqual(retrieved_events[0].position, stored_event1.position)
        self.assertEqual(retrieved_events[0].topic, stored_event1.topic)
        self.assertEqual(retrieved_events[0].state, stored_event1.state)

        # Check appending a different event at the same position in the same sequence causes an error.
        state2 = json.dumps({'name': 'value2'})
        stored_event2 = StoredIntegerSequencedEvent(
            sequence_id=stored_event1.sequence_id,
            position=stored_event1.position,
            topic=EXAMPLE_EVENT_TOPIC2,
            state=state2,
        )
        self.assertEqual(stored_event1.sequence_id, stored_event2.sequence_id)
        self.assertEqual(stored_event1.position, stored_event2.position)
        self.assertNotEqual(stored_event1.topic, stored_event2.topic)
        self.assertNotEqual(stored_event1.state, stored_event2.state)
        with self.assertRaises(IntegerSequenceError):
            self.stored_event_repo.append_integer_sequenced_event(stored_event2)

        # Check appending a different event at the same position in the same sequence causes an error.
        state2 = json.dumps({'name': 'value2'})
        stored_event2 = StoredIntegerSequencedEvent(
            sequence_id=stored_event1.sequence_id,
            position=stored_event1.position,
            topic=EXAMPLE_EVENT_TOPIC2,
            state=state2,
        )
        self.assertEqual(stored_event1.sequence_id, stored_event2.sequence_id)
        self.assertEqual(stored_event1.position, stored_event2.position)
        self.assertNotEqual(stored_event1.topic, stored_event2.topic)
        self.assertNotEqual(stored_event1.state, stored_event2.state)
        with self.assertRaises(IntegerSequenceError):
            self.stored_event_repo.append_integer_sequenced_event(stored_event2)

        # Append a second event.
        stored_event2 = StoredIntegerSequencedEvent(
            sequence_id=stored_event1.sequence_id,
            position=stored_event1.position + 1,
            topic=EXAMPLE_EVENT_TOPIC2,
            state=state2,
        )
        self.stored_event_repo.append_integer_sequenced_event(stored_event2)

        # Append a third event.
        stored_event3 = StoredIntegerSequencedEvent(
            sequence_id=stored_event1.sequence_id,
            position=stored_event2.position + 1,
            topic=EXAMPLE_EVENT_TOPIC2,
            state=state2,
        )
        self.stored_event_repo.append_integer_sequenced_event(stored_event3)

        # Get all the events.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id)
        self.assertEqual(len(retrieved_events), 3)

        # Expect a list of stored events, in sequential order.
        self.assertIsInstance(retrieved_events[0], StoredIntegerSequencedEvent)
        self.assertEqual(retrieved_events[0].sequence_id, stored_event1.sequence_id)
        self.assertEqual(retrieved_events[0].position, stored_event1.position)
        self.assertEqual(retrieved_events[0].topic, stored_event1.topic)
        self.assertEqual(retrieved_events[0].state, stored_event1.state)

        self.assertIsInstance(retrieved_events[1], StoredIntegerSequencedEvent)
        self.assertEqual(retrieved_events[1].sequence_id, stored_event2.sequence_id)
        self.assertEqual(retrieved_events[1].position, stored_event2.position)
        self.assertEqual(retrieved_events[1].topic, stored_event2.topic)
        self.assertEqual(retrieved_events[1].state, stored_event2.state)

        self.assertIsInstance(retrieved_events[2], StoredIntegerSequencedEvent)
        self.assertEqual(retrieved_events[2].sequence_id, stored_event3.sequence_id)
        self.assertEqual(retrieved_events[2].position, stored_event3.position)
        self.assertEqual(retrieved_events[2].topic, stored_event3.topic)
        self.assertEqual(retrieved_events[2].state, stored_event3.state)

        # Get all events greater than a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, gt=0)
        self.assertEqual(len(retrieved_events), 2)
        self.assertEqual(retrieved_events[0].position, 1)
        self.assertEqual(retrieved_events[1].position, 2)

        # Get all events greater then or equal to a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, gte=1)
        self.assertEqual(len(retrieved_events), 2)
        self.assertEqual(retrieved_events[0].position, 1)
        self.assertEqual(retrieved_events[1].position, 2)

        # Get all events less than a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, lt=2)
        self.assertEqual(len(retrieved_events), 2)
        self.assertEqual(retrieved_events[0].position, 0)
        self.assertEqual(retrieved_events[1].position, 1)

        # Get all events less then or equal to a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, lte=1)
        self.assertEqual(len(retrieved_events), 2)
        self.assertEqual(retrieved_events[0].position, 0)
        self.assertEqual(retrieved_events[1].position, 1)

        # Get all events greater then or equal to a position and less then or equal to a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, gte=1, lte=1)
        self.assertEqual(len(retrieved_events), 1)
        self.assertEqual(retrieved_events[0].position, 1)

        # Get all events greater then or equal to a position and less then a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, gte=1, lt=2)
        self.assertEqual(len(retrieved_events), 1)
        self.assertEqual(retrieved_events[0].position, 1)

        # Get all events greater then a position and less then or equal to a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, gt=0, lte=1)
        self.assertEqual(len(retrieved_events), 1)
        self.assertEqual(retrieved_events[0].position, 1)

        # Get all events greater a position and less a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, gt=0, lt=2)
        self.assertEqual(len(retrieved_events), 1)
        self.assertEqual(retrieved_events[0].position, 1)

        # Get all events, with a limit.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, limit=1)
        self.assertEqual(len(retrieved_events), 1)
        self.assertEqual(retrieved_events[0].position, 0)

        # Get all events, with a limit, and with descending query (so that we get the last ones).
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, limit=2,
                                                                               query_ascending=False)
        self.assertEqual(len(retrieved_events), 2)
        self.assertEqual(retrieved_events[0].position, 1)
        self.assertEqual(retrieved_events[1].position, 2)

        # Get all events, with a limit and descending query, greater than a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, limit=2, gt=1,
                                                                               query_ascending=False)
        self.assertEqual(len(retrieved_events), 1)
        self.assertEqual(retrieved_events[0].position, 2)

        # Get all events, with a limit and descending query, less than a position.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id, limit=2, lt=2,
                                                                               query_ascending=False)
        self.assertEqual(len(retrieved_events), 2)
        self.assertEqual(retrieved_events[0].position, 0)
        self.assertEqual(retrieved_events[1].position, 1)

        # Get all events in descending order, queried in ascending order.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id,
                                                                               results_ascending=False)
        self.assertEqual(len(retrieved_events), 3)
        self.assertEqual(retrieved_events[0].position, 2)
        self.assertEqual(retrieved_events[2].position, 0)

        # Get all events in descending order, queried in descending order.
        retrieved_events = self.stored_event_repo.get_integer_sequenced_events(sequence_id,
                                                                               query_ascending=False,
                                                                               results_ascending=False)
        self.assertEqual(len(retrieved_events), 3)
        self.assertEqual(retrieved_events[0].position, 2)
        self.assertEqual(retrieved_events[2].position, 0)


class StoredEventRepositoryTestCase(AbstractStoredEventRepositoryTestCase):

    def test_stored_event_repo(self):
        stored_entity_id = 'Entity::entity1'

        # Check the repo returns None for calls to get_most_recent_event() when there aren't any events.
        self.assertIsNone(self.stored_event_repo.get_most_recent_event(stored_entity_id))

        # Store an event for 'entity1'.
        stored_event1 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.example.domain_model#Example.Created',
                                    event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":3}')
        self.stored_event_repo.append(stored_event1, new_version_number=0)

        # Store another event for 'entity1'.
        stored_event2 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.example.domain_model#Example.Created',
                                    event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":4}')
        self.stored_event_repo.append(stored_event2, new_version_number=1)

        # Get all events for 'entity1'.
        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id)
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

        # Get with different combinations of query and result ascending or descending.
        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, query_ascending=True,
                                                                    results_ascending=True)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[1].event_attrs)

        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, query_ascending=True,
                                                                    results_ascending=False)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[1].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[0].event_attrs)

        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, query_ascending=False,
                                                                    results_ascending=True)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[1].event_attrs)

        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, query_ascending=False,
                                                                    results_ascending=False)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[1].event_attrs)
        self.assertEqual(stored_event2.event_topic, retrieved_events[0].event_topic)

        # Get with limit (depends on query order).
        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, limit=1, query_ascending=True)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        # - check the first retrieved event is the first event that was stored
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)

        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, limit=1, query_ascending=False)
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
        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, after=stored_event1.event_id)
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
                                         event_topic='eventsourcing.example.domain_model#Example.Created',
                                         event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":%s}' % (
                                             page_count + 10))
            stored_events.append(stored_event_i)
            self.stored_event_repo.append(stored_event_i)

        # Check we can get events after a particular event.
        last_snapshot_event = stored_events[-20]

        # start_time = datetime.datetime.now()
        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id,
                                                                    after=last_snapshot_event.event_id)
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
        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id, limit=20, query_ascending=True)
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
        retrieved_events = self.stored_event_repo.get_stored_events(stored_entity_id,
                                                                    after=retrieved_events[-1].event_id,
                                                                    limit=20, query_ascending=True)
        retrieved_events = list(retrieved_events)
        page_duration = (datetime.datetime.now() - start_time).total_seconds()
        # self.assertLess(page_duration, 0.05)
        # print("Duration: {}".format(page_duration))

        self.assertEqual(len(retrieved_events), 20)
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_events[18].event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_events[18].event_attrs, retrieved_events[0].event_attrs)

        # Check errors.
        stored_event3 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.example.domain_model#Example.Created',
                                    event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":5}')

        # Check the 'version not found error' is raised is the new version number is too hight.
        with self.assertRaises(EntityVersionNotFound):
            self.stored_event_repo.append(stored_event3, new_version_number=100)

        # Check 'concurrency error' is raised when new version number already exists.
        with self.assertRaises(ConcurrencyError):
            self.stored_event_repo.append(stored_event3, new_version_number=0)

        # Check the 'artificial_failure_rate' argument is effective.
        with self.assertRaises(DatasourceOperationError):
            self.stored_event_repo.append(stored_event3, new_version_number=2, artificial_failure_rate=1)
        self.stored_event_repo.append(stored_event3, new_version_number=2, artificial_failure_rate=0)


class IteratorTestCase(AbstractStoredEventRepositoryTestCase):
    @property
    def stored_entity_id(self):
        return 'Entity::1'

    @property
    def num_events(self):
        return 12

    @abstractproperty
    def iterator_cls(self):
        """
        Returns iterator class.
        """

    def construct_iterator(self, is_ascending, page_size, after=None, until=None, limit=None):
        return self.iterator_cls(
            repo=self.stored_event_repo,
            stored_entity_id=self.stored_entity_id,
            page_size=page_size,
            after=after,
            until=until,
            limit=limit,
            is_ascending=is_ascending,
        )

    def setup_stored_events(self):
        self.stored_events = []
        self.number_of_stored_events = 12
        for page_number in six.moves.range(self.number_of_stored_events):
            stored_event = StoredEvent(
                event_id=uuid.uuid1().hex,
                stored_entity_id=self.stored_entity_id,
                event_topic='eventsourcing.example.domain_model#Example.Created',
                event_attrs='{"a":%s,"b":2,"stored_entity_id":"%s","timestamp":%s}' % (
                    page_number, self.stored_entity_id, uuid1().hex
                )
            )
            self.stored_events.append(stored_event)
            self.stored_event_repo.append(stored_event, new_version_number=page_number)

    def test(self):
        self.setup_stored_events()

        assert isinstance(self.stored_event_repo, AbstractStoredEventRepository)
        stored_events = self.stored_event_repo.get_stored_events(stored_entity_id=self.stored_entity_id)
        stored_events = list(stored_events)
        self.assertEqual(len(stored_events), self.num_events)

        # # Check can get all events in ascending order.
        self.assert_iterator_yields_events(
            is_ascending=True,
            expect_at_start=self.stored_events[0].event_attrs,
            expect_at_end=self.stored_events[-1].event_attrs,
            expect_event_count=12,
            expect_page_count=3,
            expect_query_count=3,
            page_size=5,
        )

        # In descending order.
        self.assert_iterator_yields_events(
            is_ascending=False,
            expect_at_start=self.stored_events[-1].event_attrs,
            expect_at_end=self.stored_events[0].event_attrs,
            expect_event_count=12,
            expect_page_count=3,
            expect_query_count=3,
            page_size=5,
        )

        # Limit number of items.
        self.assert_iterator_yields_events(
            is_ascending=False,
            expect_at_start=self.stored_events[-1].event_attrs,
            expect_at_end=self.stored_events[-2].event_attrs,
            expect_event_count=2,
            expect_page_count=1,
            expect_query_count=1,
            page_size=5,
            limit=2,
        )

        # Match the page size to the number of events.
        self.assert_iterator_yields_events(
            is_ascending=True,
            expect_at_start=self.stored_events[0].event_attrs,
            expect_at_end=self.stored_events[-1].event_attrs,
            expect_event_count=12,
            expect_page_count=1,
            expect_query_count=2,
            page_size=self.num_events,
        )

        # Queries are minimised if we set a limit.
        self.assert_iterator_yields_events(
            is_ascending=True,
            expect_at_start=self.stored_events[0].event_attrs,
            expect_at_end=self.stored_events[-1].event_attrs,
            expect_event_count=12,
            expect_page_count=1,
            expect_query_count=1,
            page_size=self.num_events,
            limit=12,
        )

    def assert_iterator_yields_events(self, is_ascending, expect_at_start, expect_at_end, expect_event_count=1,
                                      expect_page_count=0, expect_query_count=0, page_size=1, limit=None):
        iterator = self.construct_iterator(is_ascending, page_size, limit=limit)
        retrieved_events = list(iterator)
        self.assertEqual(len(retrieved_events), expect_event_count, retrieved_events)
        self.assertEqual(iterator.page_counter, expect_page_count)
        self.assertEqual(iterator.query_counter, expect_query_count)
        self.assertEqual(iterator.all_event_counter, expect_event_count)
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


class PersistenceSubscribingTestCase(AbstractStoredEventRepositoryTestCase):
    """
    Base class for test cases that required a persistence subscriber.
    """

    def setUp(self):
        super(PersistenceSubscribingTestCase, self).setUp()
        # Setup the persistence subscriber.
        self.event_store = EventStore(self.stored_event_repo)
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.event_store)

    def tearDown(self):
        # Close the persistence subscriber.
        self.persistence_subscriber.close()
        super(PersistenceSubscribingTestCase, self).tearDown()
