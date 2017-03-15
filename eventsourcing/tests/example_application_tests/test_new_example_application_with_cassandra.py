from eventsourcing.tests.example_application_tests.new_base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_tests.test_cassandra_sequence_repository import \
    CassandraIntegerSequencedRepoTestCase, CassandraTimestampSequencedRepoTestCase


class TestExampleApplicationWithCassandra(CassandraIntegerSequencedRepoTestCase,
                                          CassandraTimestampSequencedRepoTestCase,
                                          ExampleApplicationTestCase):
    pass
