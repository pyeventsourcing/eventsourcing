import datetime
import json
import uuid
from abc import abstractmethod, abstractproperty
from time import time
from uuid import uuid1

import six

from eventsourcing.application.policies import PersistenceSubscriber
from eventsourcing.domain.model.events import IntegerSequencedDomainEvent, TimestampEntityEvent, \
    topic_from_domain_class
from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError, EntityVersionNotFound, \
    SequencedItemError
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository, EventStore, \
    SimpleStoredEventIterator
from eventsourcing.infrastructure.storedevents.threaded_iterator import ThreadedStoredEventIterator
from eventsourcing.infrastructure.transcoding import StoredEvent
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase


class AbstractSequencedItemRepositoryTestCase(AbstractDatastoreTestCase):
    def __init__(self, *args, **kwargs):
        super(AbstractSequencedItemRepositoryTestCase, self).__init__(*args, **kwargs)
        self._repo = None

    def setUp(self):
        super(AbstractSequencedItemRepositoryTestCase, self).setUp()
        if self.datastore is not None:
            self.datastore.setup_connection()
            self.datastore.setup_tables()

    def tearDown(self):
        self._repo = None
        if self.datastore is not None:
            self.datastore.drop_tables()
            self.datastore.drop_connection()
        super(AbstractSequencedItemRepositoryTestCase, self).tearDown()

    @property
    def sequenced_item_repo(self):
        """
        :rtype: eventsourcing.infrastructure.eventstore.AbstractSequencedItemRepository
        """
        if self._repo is None:
            self._repo = self.construct_repo()
        return self._repo

    @abstractmethod
    def construct_repo(self):
        pass

    @abstractmethod
    def construct_positions(self):
        pass

    @abstractproperty
    def EXAMPLE_EVENT_TOPIC1(self):
        pass

    @abstractproperty
    def EXAMPLE_EVENT_TOPIC2(self):
        pass

    def test(self):
        sequence_id = uuid.uuid1().hex

        # Check repo returns None when there aren't any items.
        self.assertEqual(self.sequenced_item_repo.get_items(sequence_id), [])

        position1, position2, position3 = self.construct_positions()

        self.assertLess(position1, position2)
        self.assertLess(position2, position3)

        # Append an item.
        data1 = json.dumps({'name': 'value1'})
        item_class = self.sequenced_item_repo.active_record_strategy.sequenced_item_class
        item1 = item_class(
            sequence_id=sequence_id,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC1,
            data=data1,
        )
        self.sequenced_item_repo.append_item(item1)

        # Check repo returns the item.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id)
        self.assertEqual(len(retrieved_items), 1)
        self.assertIsInstance(retrieved_items[0], item_class)
        self.assertEqual(retrieved_items[0].sequence_id, item1.sequence_id)
        self.assertEqual(retrieved_items[0].position, position1)
        self.assertEqual(retrieved_items[0].data, item1.data)
        self.assertEqual(retrieved_items[0].topic, item1.topic)

        # Check appending a different item at the same position in the same sequence causes an error.
        data2 = json.dumps({'name': 'value2'})
        item2 = item_class(
            sequence_id=item1.sequence_id,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            data=data2,
        )
        self.assertEqual(item1.sequence_id, item2.sequence_id)
        self.assertEqual(position1, item2.position)
        self.assertNotEqual(item1.topic, item2.topic)
        self.assertNotEqual(item1.data, item2.data)
        with self.assertRaises(SequencedItemError):
            self.sequenced_item_repo.append_item(item2)

        # Check appending a different item at the same position in the same sequence causes an error.
        data2 = json.dumps({'name': 'value2'})
        item3 = item_class(
            sequence_id=item1.sequence_id,
            position=position1,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            data=data2,
        )
        with self.assertRaises(SequencedItemError):
            self.sequenced_item_repo.append_item(item3)

        # Append a second item at the next position.
        item4 = item_class(
            sequence_id=item1.sequence_id,
            position=position2,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            data=data2,
        )
        self.sequenced_item_repo.append_item(item4)

        # Check there are two items.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id)
        self.assertEqual(len(retrieved_items), 2)

        # Append a third item.
        item5 = item_class(
            sequence_id=item1.sequence_id,
            position=position3,
            topic=self.EXAMPLE_EVENT_TOPIC2,
            data=data2,
        )
        self.sequenced_item_repo.append_item(item5)

        # Check there are three items.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id)
        self.assertEqual(len(retrieved_items), 3)

        # Check the items are in sequential order.
        self.assertIsInstance(retrieved_items[0], item_class)
        self.assertEqual(retrieved_items[0].sequence_id, item1.sequence_id)
        self.assertEqual(retrieved_items[0].position, position1)
        self.assertEqual(retrieved_items[0].topic, item1.topic)
        self.assertEqual(retrieved_items[0].data, item1.data)

        self.assertIsInstance(retrieved_items[1], item_class)
        self.assertEqual(retrieved_items[1].sequence_id, item2.sequence_id)
        self.assertEqual(retrieved_items[1].position, position2)
        self.assertEqual(retrieved_items[1].topic, item2.topic)
        self.assertEqual(retrieved_items[1].data, item2.data)

        self.assertIsInstance(retrieved_items[2], item_class)
        self.assertEqual(retrieved_items[2].sequence_id, item5.sequence_id)
        self.assertEqual(retrieved_items[2].position, position3)
        self.assertEqual(retrieved_items[2].topic, item5.topic)
        self.assertEqual(retrieved_items[2].data, item5.data)

        # Get all items greater than a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, gt=position1)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].position, position2)
        self.assertEqual(retrieved_items[1].position, position3)

        # Get all items greater then or equal to a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, gte=position2)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].position, position2)
        self.assertEqual(retrieved_items[1].position, position3)

        # Get all items less than a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, lt=position3)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].position, position1)
        self.assertEqual(retrieved_items[1].position, position2)

        # Get all items less then or equal to a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, lte=position2)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].position, position1)
        self.assertEqual(retrieved_items[1].position, position2)

        # Get all items greater then or equal to a position and less then or equal to a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, gte=position2, lte=position2)
        self.assertEqual(len(retrieved_items), 1)
        self.assertEqual(retrieved_items[0].position, position2)

        # Get all items greater then or equal to a position and less then a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, gte=position2, lt=position3)
        self.assertEqual(len(retrieved_items), 1)
        self.assertEqual(retrieved_items[0].position, position2)

        # Get all items greater then a position and less then or equal to a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, gt=position1, lte=position2)
        self.assertEqual(len(retrieved_items), 1)
        self.assertEqual(retrieved_items[0].position, position2)

        # Get all items greater a position and less a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, gt=position1, lt=position3)
        self.assertEqual(len(retrieved_items), 1)
        self.assertEqual(retrieved_items[0].position, position2)

        # Get all items, with a limit.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, limit=1)
        self.assertEqual(len(retrieved_items), 1)
        self.assertEqual(retrieved_items[0].position, position1)

        # Get all items, with a limit, and with descending query (so that we get the last ones).
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, limit=2,
                                                             query_ascending=False)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].position, position2)
        self.assertEqual(retrieved_items[1].position, position3)

        # Get all items, with a limit and descending query, greater than a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, limit=2, gt=position2,
                                                             query_ascending=False)
        self.assertEqual(len(retrieved_items), 1)
        self.assertEqual(retrieved_items[0].position, position3)

        # Get all items, with a limit and descending query, less than a position.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id, limit=2, lt=position3,
                                                             query_ascending=False)
        self.assertEqual(len(retrieved_items), 2)
        self.assertEqual(retrieved_items[0].position, position1)
        self.assertEqual(retrieved_items[1].position, position2)

        # Get all items in descending order, queried in ascending order.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id,
                                                             results_ascending=False)
        self.assertEqual(len(retrieved_items), 3)
        self.assertEqual(retrieved_items[0].position, position3)
        self.assertEqual(retrieved_items[2].position, position1)

        # Get all items in descending order, queried in descending order.
        retrieved_items = self.sequenced_item_repo.get_items(sequence_id,
                                                             query_ascending=False,
                                                             results_ascending=False)
        self.assertEqual(len(retrieved_items), 3)
        self.assertEqual(retrieved_items[0].position, position3)
        self.assertEqual(retrieved_items[2].position, position1)


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
    def sequenced_item_repo(self):
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


class ExampleIntegerSequencedEvent1(IntegerSequencedDomainEvent):
    pass


class ExampleIntegerSequencedEvent2(IntegerSequencedDomainEvent):
    pass


class ExampleTimeSequencedEvent1(TimestampEntityEvent):
    pass


class ExampleTimeSequencedEvent2(TimestampEntityEvent):
    pass


class IntegerSequencedItemRepositoryTestCase(AbstractSequencedItemRepositoryTestCase):
    EXAMPLE_EVENT_TOPIC1 = topic_from_domain_class(ExampleIntegerSequencedEvent1)
    EXAMPLE_EVENT_TOPIC2 = topic_from_domain_class(ExampleIntegerSequencedEvent2)

    def construct_positions(self):
        return 0, 1, 2


class TimeSequencedItemRepositoryTestCase(AbstractSequencedItemRepositoryTestCase):
    EXAMPLE_EVENT_TOPIC1 = topic_from_domain_class(ExampleTimeSequencedEvent1)
    EXAMPLE_EVENT_TOPIC2 = topic_from_domain_class(ExampleTimeSequencedEvent2)

    def construct_positions(self):
        t1 = time()
        return t1, t1 + 0.00001, t1 + 0.00002


class StoredEventRepositoryTestCase(AbstractStoredEventRepositoryTestCase):
    def test_stored_event_repo(self):
        stored_entity_id = 'Entity::entity1'

        # Check the repo returns None for calls to get_most_recent_event() when there aren't any events.
        self.assertIsNone(self.sequenced_item_repo.get_most_recent_event(stored_entity_id))

        # Store an event for 'entity1'.
        stored_event1 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.example.domain_model#Example.Created',
                                    event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":3}')
        self.sequenced_item_repo.append(stored_event1, new_version_number=0)

        # Store another event for 'entity1'.
        stored_event2 = StoredEvent(event_id=uuid.uuid1().hex,
                                    stored_entity_id=stored_entity_id,
                                    event_topic='eventsourcing.example.domain_model#Example.Created',
                                    event_attrs='{"a":1,"b":2,"stored_entity_id":"entity1","timestamp":4}')
        self.sequenced_item_repo.append(stored_event2, new_version_number=1)

        # Get all events for 'entity1'.
        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id)
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
        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, query_ascending=True,
                                                                      results_ascending=True)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[1].event_attrs)

        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, query_ascending=True,
                                                                      results_ascending=False)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[1].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[0].event_attrs)

        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, query_ascending=False,
                                                                      results_ascending=True)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[1].event_attrs)

        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, query_ascending=False,
                                                                      results_ascending=False)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[1].event_attrs)
        self.assertEqual(stored_event2.event_topic, retrieved_events[0].event_topic)

        # Get with limit (depends on query order).
        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, limit=1, query_ascending=True)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        # - check the first retrieved event is the first event that was stored
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event1.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)

        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, limit=1, query_ascending=False)
        retrieved_events = list(retrieved_events)  # Make sequence from the iterator.
        # - check the first retrieved event is the last event that was stored
        self.assertIsInstance(retrieved_events[0], StoredEvent)
        self.assertEqual(stored_event2.event_topic, retrieved_events[0].event_topic)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[0].event_attrs)

        # Get the most recent event for 'entity1'.
        most_recent_event = self.sequenced_item_repo.get_most_recent_event(stored_entity_id)
        self.assertIsInstance(most_recent_event, StoredEvent)
        self.assertEqual(most_recent_event.event_id, stored_event2.event_id)

        # Get all events for 'entity1' since the first event's timestamp.
        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, after=stored_event1.event_id)
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
            self.sequenced_item_repo.append(stored_event_i)

        # Check we can get events after a particular event.
        last_snapshot_event = stored_events[-20]

        # start_time = datetime.datetime.now()
        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id,
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
        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id, limit=20, query_ascending=True)
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
        retrieved_events = self.sequenced_item_repo.get_stored_events(stored_entity_id,
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
            self.sequenced_item_repo.append(stored_event3, new_version_number=100)

        # Check 'concurrency error' is raised when new version number already exists.
        with self.assertRaises(ConcurrencyError):
            self.sequenced_item_repo.append(stored_event3, new_version_number=0)

        # Check the 'artificial_failure_rate' argument is effective.
        with self.assertRaises(DatasourceOperationError):
            self.sequenced_item_repo.append(stored_event3, new_version_number=2, artificial_failure_rate=1)
        self.sequenced_item_repo.append(stored_event3, new_version_number=2, artificial_failure_rate=0)


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
            repo=self.sequenced_item_repo,
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
            self.sequenced_item_repo.append(stored_event, new_version_number=page_number)

    def test(self):
        self.setup_stored_events()

        assert isinstance(self.sequenced_item_repo, AbstractStoredEventRepository)
        stored_events = self.sequenced_item_repo.get_stored_events(stored_entity_id=self.stored_entity_id)
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
        self.event_store = EventStore(self.sequenced_item_repo)
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.event_store)

    def tearDown(self):
        # Close the persistence subscriber.
        self.persistence_subscriber.close()
        super(PersistenceSubscribingTestCase, self).tearDown()
