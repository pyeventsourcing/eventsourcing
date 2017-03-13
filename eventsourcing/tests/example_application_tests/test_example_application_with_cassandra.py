from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase, \
    NewExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_repository_tests.test_cassandra_sequence_repository import \
    CassandraIntegerSequencedRepoTestCase, CassandraRepoTestCase


class TestNewExampleApplicationWithCassandra(CassandraIntegerSequencedRepoTestCase,
                                             NewExampleApplicationTestCase):
    pass


class TestExampleApplicationWithCassandra(CassandraRepoTestCase, ExampleApplicationTestCase):
    pass
