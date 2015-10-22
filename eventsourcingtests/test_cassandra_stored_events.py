from eventsourcing.infrastructure.stored_events.cassandra_stored_events import CassandraStoredEventRepository, \
    setup_cassandra_connection, shutdown_cassandra_connection, get_cassandra_setup_params, CqlStoredEvent
from eventsourcingtests.test_stored_events import StoredEventRepositoryTestCase


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

