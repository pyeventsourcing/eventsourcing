from cassandra.cqlengine.management import drop_keyspace

from eventsourcing.application.with_cassandra import DEFAULT_CASSANDRA_KEYSPACE
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import CassandraStoredEventRepository, \
    setup_cassandra_connection, shutdown_cassandra_connection, get_cassandra_setup_params, \
    create_cassandra_keyspace_and_tables
from eventsourcingtests.test_stored_events import StoredEventRepositoryTestCase


class TestCassandraStoredEventRepository(StoredEventRepositoryTestCase):

    def setUp(self):
        super(TestCassandraStoredEventRepository, self).setUp()
        setup_cassandra_connection(*get_cassandra_setup_params(default_keyspace=DEFAULT_CASSANDRA_KEYSPACE))
        create_cassandra_keyspace_and_tables(DEFAULT_CASSANDRA_KEYSPACE)

    def tearDown(self):
        drop_keyspace(DEFAULT_CASSANDRA_KEYSPACE)
        shutdown_cassandra_connection()
        super(TestCassandraStoredEventRepository, self).tearDown()

    def test_stored_events_in_cassandra(self):
        stored_event_repo = CassandraStoredEventRepository()
        self.checkStoredEventRepository(stored_event_repo)
