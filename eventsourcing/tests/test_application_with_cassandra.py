from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import create_cassandra_keyspace_and_tables, \
    drop_cassandra_keyspace
from eventsourcing.tests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithCassandra(ExampleApplicationTestCase):

    def create_app(self):
        return ExampleApplicationWithCassandra()

    def setUp(self):
        super(TestApplicationWithCassandra, self).setUp()
        create_cassandra_keyspace_and_tables()

    def tearDown(self):
        drop_cassandra_keyspace()
        super(TestApplicationWithCassandra, self).tearDown()
