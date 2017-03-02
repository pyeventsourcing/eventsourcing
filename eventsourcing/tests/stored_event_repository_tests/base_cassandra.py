from eventsourcing.infrastructure.datastore.cassandra import CassandraDatastoreStrategy, CassandraSettings
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CassandraStoredEventRepository, \
    CqlStoredEvent, CqlEntityVersion
from eventsourcing.tests.stored_event_repository_tests.base import AbstractStoredEventRepositoryTestCase
from eventsourcing.tests.base import AbstractTestCase


class CassandraTestCase(AbstractTestCase):
    """
    Uses the datastore object to set up connection to and tables in Cassandra.
    """
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


class CassandraRepoTestCase(CassandraTestCase, AbstractStoredEventRepositoryTestCase):
    """
    Implements the stored_event_repo property, by
    providing a Cassandra stored event repository.
    """
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


def create_cassandra_datastore_strategy():
    return CassandraDatastoreStrategy(
        settings=CassandraSettings(),
        tables=(CqlStoredEvent, CqlEntityVersion),
    )
