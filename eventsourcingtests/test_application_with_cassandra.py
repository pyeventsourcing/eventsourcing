from cassandra.cqlengine.management import drop_keyspace

from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.application.with_cassandra import DEFAULT_CASSANDRA_KEYSPACE
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import create_cassandra_keyspace_and_tables
from eventsourcingtests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithCassandra(ExampleApplicationTestCase):

    def test_application_with_cassandra(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithCassandra() as app:
            create_cassandra_keyspace_and_tables(DEFAULT_CASSANDRA_KEYSPACE)
            try:
                self.assert_is_example_application(app)
            finally:
                drop_keyspace(DEFAULT_CASSANDRA_KEYSPACE)
