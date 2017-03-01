from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.infrastructure.cassandra import CassandraDatastoreStrategy, CassandraSettings
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CqlStoredEvent, \
    CassandraStoredEventRepository
from eventsourcing.tests.unit_test_cases_example_application import ExampleApplicationTestCase


class TestExampleApplicationWithCassandra(ExampleApplicationTestCase):

    def setUp(self):
        self.datastore_strategy = create_cassandra_datastore_strategy()
        self.datastore_strategy.setup_connection()
        self.datastore_strategy.setup_tables()
        super(TestExampleApplicationWithCassandra, self).setUp()

    def create_app(self):
        return create_example_application_with_cassandra()

    def tearDown(self):
        super(TestExampleApplicationWithCassandra, self).tearDown()
        self.datastore_strategy.drop_tables()
        self.datastore_strategy.drop_connection()


def create_example_application_with_cassandra(cipher=None):
    return ExampleApplication(
        stored_event_repository=CassandraStoredEventRepository(
            stored_event_table=CqlStoredEvent
        ),
        cipher=cipher,
    )


def create_cassandra_datastore_strategy():
    return CassandraDatastoreStrategy(
        settings=CassandraSettings(),
        tables=(CqlStoredEvent,),
    )
