from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import create_cassandra_keyspace_and_tables, \
    drop_cassandra_keyspace
from eventsourcing.tests.unit_test_cases_cassandra import CassandraTestCase
from eventsourcing.tests.unit_test_cases_example_application import ExampleApplicationTestCase


class TestApplicationWithCassandra(CassandraTestCase, ExampleApplicationTestCase):

    def create_app(self):
        return ExampleApplicationWithCassandra()

    def setUp(self):
        super(TestApplicationWithCassandra, self).setUp()
        create_cassandra_keyspace_and_tables()

    def tearDown(self):
        drop_cassandra_keyspace()
        super(TestApplicationWithCassandra, self).tearDown()
