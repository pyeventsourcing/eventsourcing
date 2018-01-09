from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_tests.test_cassandra_record_manager import \
    WithCassandraRecordManagers


class TestExampleApplicationWithCassandra(WithCassandraRecordManagers, ExampleApplicationTestCase):
    pass
