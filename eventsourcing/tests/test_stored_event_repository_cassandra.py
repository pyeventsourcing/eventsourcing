import unittest

from eventsourcing.tests.test_stored_events import BasicStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase, ConcurrentStoredEventRepositoryTestCase
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import CassandraStoredEventRepository, \
    setup_cassandra_connection, get_cassandra_setup_params, create_cassandra_keyspace_and_tables, \
    drop_cassandra_keyspace


class CassandraTestCase(unittest.TestCase):

    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            stored_event_repo = CassandraStoredEventRepository()
            self._stored_event_repo = stored_event_repo
            return stored_event_repo

    def setUp(self):
        super(CassandraTestCase, self).setUp()
        setup_cassandra_connection(*get_cassandra_setup_params())
        create_cassandra_keyspace_and_tables()

    def tearDown(self):
        drop_cassandra_keyspace()
        # shutdown_cassandra_connection()
        super(CassandraTestCase, self).tearDown()


class TestCassandraStoredEventRepository(CassandraTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraTestCase, ThreadedStoredEventIteratorTestCase):
    pass


class TestConcurrentStoredEventRepositoryWithCassandra(CassandraTestCase, ConcurrentStoredEventRepositoryTestCase):
    pass
