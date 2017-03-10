import datetime
import json
import os
import traceback
import uuid
from abc import abstractmethod, abstractproperty
from multiprocessing.pool import Pool
from time import sleep
from uuid import uuid1, uuid4

import six

from eventsourcing.application.policies import PersistenceSubscriber
from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError, EntityVersionNotFound
from eventsourcing.infrastructure.datastore.cassandraengine import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.datastore.sqlalchemyorm import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository, EventStore, \
    SimpleStoredEventIterator
from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, \
    CqlStoredEvent
from eventsourcing.infrastructure.storedevents.pythonobjectsrepo import PythonObjectsStoredEventRepository
from eventsourcing.infrastructure.storedevents.sqlalchemyrepo import SQLAlchemyStoredEventRepository, \
    SqlStoredEvent
from eventsourcing.infrastructure.storedevents.threaded_iterator import ThreadedStoredEventIterator
from eventsourcing.infrastructure.transcoding import StoredEvent
from eventsourcing.tests.base import notquick
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
from eventsourcing.tests.datastore_tests.test_cassandra import DEFAULT_KEYSPACE_FOR_TESTING


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



class OptimisticConcurrencyControlTestCase(AbstractStoredEventRepositoryTestCase):
    @notquick()
    def test_optimistic_concurrency_control(self):
        """Appends lots of events, but with a pool of workers
        all trying to add the same sequence of events.
        """
        # Start a pool.
        pool_size = 3
        print("Pool size: {}".format(pool_size))

        # Erm, this is only needed for SQLite database file.
        # Todo: Maybe factor out a 'get_initargs()' method on this class,
        # so this detail is localised to the test cases that need it.
        if hasattr(self, 'temp_file'):
            temp_file_name = getattr(self, 'temp_file').name
        else:
            temp_file_name = None

        pool = Pool(
            initializer=pool_initializer,
            processes=pool_size,
            initargs=(type(self.stored_event_repo), temp_file_name),
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

        # Check there was contention that caused at least one concurrency error.
        set_failures = set([i[0] for i in total_failures])
        self.assertTrue(len(set_failures))

        # Check each child wrote at least one event.
        self.assertEqual(len(set([i[1] for i in total_successes])), pool_size)

        # Check each child encountered at least one concurrency error.
        self.assertEqual(len(set([i[1] for i in total_failures])), pool_size)

        # Check the repo actually has a contiguous version sequence.
        events = self.stored_event_repo.get_stored_events(stored_entity_id)
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
        assert isinstance(num_events_to_create, six.integer_types)

        successes = []
        failures = []

        try:

            while True:
                # Imitate an entity getting refreshed, by getting the version of the last event.
                assert isinstance(worker_repo, AbstractStoredEventRepository)
                events = worker_repo.get_stored_events(stored_entity_id, limit=1, query_ascending=False)
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
                except DatasourceOperationError:
                    # print("PID {} got concurrent exception writing event at version {} at {}".format(
                    #     pid, new_version, started, datetime.datetime.now() - started))
                    # failures.append((new_version, pid))
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


worker_repo = None


def pool_initializer(stored_repo_class, temp_file_name):
    global worker_repo
    worker_repo = construct_repo_for_worker(stored_repo_class, temp_file_name)


def construct_repo_for_worker(stored_repo_class, temp_file_name):
    if stored_repo_class is CassandraStoredEventRepository:
        datastore = CassandraDatastore(
            settings=CassandraSettings(default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING),
            tables=(CqlStoredEvent,)
        )
        datastore.drop_connection()
        datastore.setup_connection()
        repo = CassandraStoredEventRepository(
            stored_event_table=CqlStoredEvent,
            always_check_expected_version=True,
            always_write_entity_version=True,
        )
    elif stored_repo_class is SQLAlchemyStoredEventRepository:
        uri = 'sqlite:///' + temp_file_name
        datastore = SQLAlchemyDatastore(
            settings=SQLAlchemySettings(uri=uri),
            tables=(SqlStoredEvent,),
        )
        datastore.setup_connection()
        repo = SQLAlchemyStoredEventRepository(
            datastore=datastore,
            stored_event_table=SqlStoredEvent,
            always_check_expected_version=True,
            always_write_entity_version=True,
        )
    elif stored_repo_class is PythonObjectsStoredEventRepository:
        repo = PythonObjectsStoredEventRepository(
            always_check_expected_version=True,
            always_write_entity_version=True,
        )
    else:
        raise Exception("Stored repo class not yet supported in test: {}".format(stored_repo_class))
    return repo


def append_lots_of_events_to_repo(args):
    return OptimisticConcurrencyControlTestCase.append_lots_of_events_to_repo(args)


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
