from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CassandraStoredEventRepository, \
    CqlStoredEvent
from eventsourcing.tests.example_application_tests.test_example_application_with_cassandra import \
    create_cassandra_datastore_strategy
from eventsourcing.tests.unit_test_cases import AbstractTestCase


class CassandraTestCase(AbstractTestCase):
    def setUp(self):
        super(CassandraTestCase, self).setUp()
        # Setup the keyspace and column family for stored events.
        self.datastore = create_cassandra_datastore_strategy()
        self.datastore.setup_connection()
        self.datastore.drop_tables()
        self.datastore.setup_tables()

    def tearDown(self):
        # Drop the keyspace.
        self.datastore.drop_tables()
        self.datastore.drop_connection()
        super(CassandraTestCase, self).tearDown()


class CassandraRepoTestCase(CassandraTestCase):
    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            stored_event_repo = CassandraStoredEventRepository(
                stored_event_table=CqlStoredEvent,
                always_write_entity_version=True,
                always_check_expected_version=True,
            )
            self._stored_event_repo = stored_event_repo
            return stored_event_repo
