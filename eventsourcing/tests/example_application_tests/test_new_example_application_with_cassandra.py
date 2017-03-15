from eventsourcing.tests.example_application_tests.new_base import ExampleApplicationTestCase
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    CassandraActiveRecordStrategies


class TestExampleApplicationWithCassandra(CassandraActiveRecordStrategies, ExampleApplicationTestCase):
    pass
