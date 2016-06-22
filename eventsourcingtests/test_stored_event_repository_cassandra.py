import unittest

from cassandra.cqlengine.management import drop_keyspace

from eventsourcing.application.with_cassandra import DEFAULT_CASSANDRA_KEYSPACE
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import CassandraStoredEventRepository, \
    setup_cassandra_connection, shutdown_cassandra_connection, get_cassandra_setup_params, \
    create_cassandra_keyspace_and_tables
from eventsourcingtests.test_stored_events import BasicStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase


class CassandraTestCase(unittest.TestCase):

    @property
    def stored_event_repo(self):
        return CassandraStoredEventRepository()

    def setUp(self):
        super(CassandraTestCase, self).setUp()
        setup_cassandra_connection(*get_cassandra_setup_params(default_keyspace=DEFAULT_CASSANDRA_KEYSPACE))
        create_cassandra_keyspace_and_tables(DEFAULT_CASSANDRA_KEYSPACE)

    def tearDown(self):
        drop_keyspace(DEFAULT_CASSANDRA_KEYSPACE)
        shutdown_cassandra_connection()
        super(CassandraTestCase, self).tearDown()


class TestCassandraStoredEventRepository(CassandraTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraTestCase, ThreadedStoredEventIteratorTestCase):
    pass
