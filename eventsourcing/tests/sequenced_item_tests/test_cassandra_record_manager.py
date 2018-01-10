from eventsourcing.infrastructure.cassandra.factory import construct_integer_sequenced_record_manager, \
    construct_snapshot_record_manager, construct_timestamp_sequenced_record_manager
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase, \
    WithActiveRecordManagers


class TestCassandraRecordManagerWithIntegerSequences(CassandraDatastoreTestCase,
                                                     IntegerSequencedItemTestCase):
    def construct_record_manager(self):
        return construct_integer_sequenced_record_manager()


class TestCassandraRecordManagerWithTimestampSequences(CassandraDatastoreTestCase,
                                                       TimestampSequencedItemTestCase):
    def construct_record_manager(self):
        return construct_timestamp_sequenced_record_manager()


class WithCassandraRecordManagers(CassandraDatastoreTestCase, WithActiveRecordManagers):
    def construct_entity_record_manager(self):
        return construct_integer_sequenced_record_manager()

    def construct_log_record_manager(self):
        return construct_timestamp_sequenced_record_manager()

    def construct_snapshot_record_manager(self):
        return construct_snapshot_record_manager()


class TestSimpleSequencedItemIteratorWithCassandra(WithCassandraRecordManagers,
                                                   SimpleSequencedItemteratorTestCase):
    pass


class TestThreadedSequencedItemIteratorWithCassandra(WithCassandraRecordManagers,
                                                     ThreadedSequencedItemIteratorTestCase):
    pass
