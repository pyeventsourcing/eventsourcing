from eventsourcing.tests.example_application_tests import base
from eventsourcing.tests.sequenced_item_tests.test_cassandra_record_manager import \
    WithCassandraRecordManagers


class TestExampleApplicationWithCassandra(WithCassandraRecordManagers, base.ExampleApplicationTestCase):
    pass
