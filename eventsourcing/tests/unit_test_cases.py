import datetime
import json
import os
import traceback
import uuid
from multiprocessing.pool import Pool
from tempfile import NamedTemporaryFile
from time import sleep
from unittest import TestCase
from uuid import uuid4, uuid1

import six

from eventsourcing.domain.services.eventstore import AbstractStoredEventRepository, SimpleStoredEventIterator
from eventsourcing.domain.services.transcoding import StoredEvent
from eventsourcing.exceptions import ConcurrencyError
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CassandraStoredEventRepository, \
    setup_cassandra_connection, get_cassandra_setup_params
from eventsourcing.infrastructure.stored_event_repos.with_python_objects import PythonObjectsStoredEventRepository
from eventsourcing.infrastructure.stored_event_repos.with_sqlalchemy import SQLAlchemyStoredEventRepository, \
    get_scoped_session_facade
from eventsourcing.infrastructure.stored_event_repos.threaded_iterator import ThreadedStoredEventIterator


class AbstractTestCase(TestCase):

    def setUp(self):
        """
        Returns None if test case class ends with 'TestCase', which means the test case isn't included in the suite.
        """
        if type(self).__name__.endswith('TestCase'):
            self.skipTest('Skipped abstract test')
        else:
            super(AbstractTestCase, self).setUp()


class AbstractStoredEventRepositoryTestCase(AbstractTestCase):

    @property
    def stored_event_repo(self):
        """
        :rtype: AbstractStoredEventRepository
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

        # Get with different combinations of query and result ascending or descending.
        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, query_ascending=True, results_ascending=True)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[1].event_attrs)

        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, query_ascending=True, results_ascending=False)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[1].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[0].event_attrs)

        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, query_ascending=False, results_ascending=True)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[0].event_attrs)
        self.assertEqual(stored_event2.event_attrs, retrieved_events[1].event_attrs)

        retrieved_events = self.stored_event_repo.get_entity_events(stored_entity_id, query_ascending=False, results_ascending=False)
        retrieved_events = list(retrieved_events)
        self.assertEqual(stored_event1.event_attrs, retrieved_events[1].event_attrs)
        self.assertEqual(stored_event2.event_topic, retrieved_events[0].event_topic)

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


class ConcurrentStoredEventRepositoryTestCase(AbstractStoredEventRepositoryTestCase):

    def setUp(self):
        super(ConcurrentStoredEventRepositoryTestCase, self).setUp()
        self.app = None
        self.temp_file = NamedTemporaryFile('a')

    def tearDown(self):
        super(ConcurrentStoredEventRepositoryTestCase, self).tearDown()
        if self.app is not None:
            self.app.close()

    def test_optimistic_concurrency_control(self):
        """Appends lots of events, but with a pool of workers
        all trying to add the same sequence of events.
        """
        # Start a pool.
        pool_size = 3
        print("Pool size: {}".format(pool_size))
        pool = Pool(
            initializer=pool_initializer,
            processes=pool_size,
            initargs=(type(self.stored_event_repo), self.temp_file.name),
        )

        # Append duplicate events to the repo, or at least try...
        number_of_events = 40
        self.assertGreater(number_of_events, pool_size)
        stored_entity_id = uuid4().hex
        sequence_of_args = [(number_of_events, stored_entity_id)] * pool_size
        results = pool.map(append_lots_of_events_to_repo, sequence_of_args)
        total_successes = []
        total_failures = []
        for result in results:
            if isinstance(result, Exception):
                print(result.args[0][1])
                raise result
            else:
                successes, failures = result
                assert isinstance(successes, list), result
                assert isinstance(failures, list), result
                total_successes.extend(successes)
                total_failures.extend(failures)

        # Close the pool.
        pool.close()

        # Check each event version was written exactly once.
        self.assertEqual(sorted([i[0] for i in total_successes]), list(range(number_of_events)))

        # Check each child got to write at least one event.
        self.assertEqual(len(set([i[1] for i in total_successes])), pool_size)

        # Check each event version at least once wasn't written due to a concurrency error.
        self.assertEqual(sorted(set(sorted([i[0] for i in total_failures]))), list(range(number_of_events)))

        # Check at least one event version wasn't written due to a concurrency error.
        self.assertTrue(set([i[0] for i in total_failures]))

        # Check each child failed to write at least one event.
        self.assertEqual(len(set([i[1] for i in total_failures])), pool_size)

        # Check there's actually a contiguous version sequence through the sequence of stored events.
        events = self.stored_event_repo.get_entity_events(stored_entity_id)
        self.assertEqual(len(events), number_of_events)
        version_counter = 0
        for event in events:
            assert isinstance(event, StoredEvent)
            attr_values = json.loads(event.event_attrs)
            self.assertEqual(attr_values['entity_version'], version_counter)
            version_counter += 1

        # Join the pool.
        pool.join()

    @staticmethod
    def append_lots_of_events_to_repo(args):

        num_events_to_create, stored_entity_id = args

        success_count = 0
        assert isinstance(worker_repo, AbstractStoredEventRepository)
        assert isinstance(num_events_to_create, six.integer_types)

        successes = []
        failures = []

        try:

            while True:
                # Imitate an entity getting refreshed, by getting the version of the last event.
                events = worker_repo.get_entity_events(stored_entity_id, limit=1, query_ascending=False)
                if len(events):
                    current_version = json.loads(events[0].event_attrs)['entity_version']
                    new_version = current_version + 1
                else:
                    current_version = None
                    new_version = 0

                # Stop before the version number gets too high.
                if new_version >= num_events_to_create:
                    break

                pid = os.getpid()
                try:

                    # Append an event.
                    stored_event = StoredEvent(
                        event_id=uuid1().hex,
                        stored_entity_id=stored_entity_id,
                        event_topic='topic',
                        event_attrs=json.dumps({'a': 1, 'b': 2, 'entity_version': new_version}),
                    )
                    started = datetime.datetime.now()
                    worker_repo.append(
                        new_stored_event=stored_event,
                        new_version_number=new_version,
                        max_retries=10,
                        artificial_failure_rate=0.25,
                    )
                except ConcurrencyError:
                    # print("PID {} got concurrent exception writing event at version {} at {}".format(
                    #     pid, new_version, started, datetime.datetime.now() - started))
                    failures.append((new_version, pid))
                    sleep(0.01)
                else:
                    print("PID {} success writing event at version {} at {} in {}".format(
                        pid, new_version, started, datetime.datetime.now() - started))
                    success_count += 1
                    successes.append((new_version, pid))
                    # Delay a successful writer, to give other processes a chance to write the next event.
                    sleep(0.03)

        # Return to parent process the successes and failure, or an exception.
        except Exception as e:
            msg = traceback.format_exc()
            print(" - failed to append event: {}".format(msg))
            return Exception((e, msg))
        else:
            return (successes, failures)


def pool_initializer(stored_repo_class, temp_file_name):
    global worker_repo

    repo = create_repo(stored_repo_class, temp_file_name)
    worker_repo = repo


def append_lots_of_events_to_repo(args):
    return ConcurrentStoredEventRepositoryTestCase.append_lots_of_events_to_repo(args)


worker_repo = None


def create_repo(stored_repo_class, temp_file_name):
    if stored_repo_class == CassandraStoredEventRepository:
        setup_cassandra_connection(*get_cassandra_setup_params())
        repo = CassandraStoredEventRepository(
            always_check_expected_version=True,
            always_write_entity_version=True,
        )
    elif stored_repo_class == SQLAlchemyStoredEventRepository:
        uri = 'sqlite:///' + temp_file_name
        scoped_session_facade = get_scoped_session_facade(uri)
        repo = SQLAlchemyStoredEventRepository(scoped_session_facade,
            always_check_expected_version=True,
            always_write_entity_version=True,
        )
    elif stored_repo_class == PythonObjectsStoredEventRepository:
        repo = PythonObjectsStoredEventRepository(
            always_check_expected_version=True,
            always_write_entity_version=True,
        )
    else:
        raise Exception("Stored repo class not yet supported in test: {}".format(stored_repo_class))
    return repo


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

        assert isinstance(self.stored_event_repo, AbstractStoredEventRepository)
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