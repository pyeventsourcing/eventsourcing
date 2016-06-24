from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import create_cassandra_keyspace_and_tables, \
    drop_cassandra_keyspace
from eventsourcingtests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithCassandra(ExampleApplicationTestCase):

    def test_application_with_cassandra(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithCassandra() as app:
            create_cassandra_keyspace_and_tables()
            try:
                self.assert_is_example_application(app)
            finally:
                drop_cassandra_keyspace()
