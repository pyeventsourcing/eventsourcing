from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.infrastructure.cassandra import CassandraDatastoreStrategy, CassandraSettings
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CqlStoredEvent, \
    CassandraStoredEventRepository
from eventsourcing.tests.unit_test_cases_example_application import ExampleApplicationTestCase


class TestExampleApplicationWithCassandra(ExampleApplicationTestCase):

    def setUp(self):
        self.datastore_strategy = CassandraDatastoreStrategy(
            settings=CassandraSettings(),
            tables=(CqlStoredEvent,),
        )
        self.datastore_strategy.setup_connection()
        self.datastore_strategy.setup_tables()
        super(TestExampleApplicationWithCassandra, self).setUp()

    def create_app(self):
        return ExampleApplication(
            stored_event_repository=CassandraStoredEventRepository(
                stored_event_table=CqlStoredEvent
            ),
        )

    def tearDown(self):
        super(TestExampleApplicationWithCassandra, self).tearDown()
        self.datastore_strategy.drop_tables()
        self.datastore_strategy.drop_connection()
