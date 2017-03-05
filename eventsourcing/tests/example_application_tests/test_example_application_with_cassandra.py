from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.stored_event_repository_tests.test_cassandra_stored_event_repository import \
    CassandraRepoTestCase


class TestExampleApplicationWithCassandra(CassandraRepoTestCase, ExampleApplicationTestCase):
    pass
