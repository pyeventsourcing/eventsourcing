from eventsourcing.infrastructure.cassandra.models import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord

from eventsourcing.infrastructure.cassandra.strategy import CassandraRecordManager
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase, \
    WithActiveRecordManagers


def construct_integer_sequenced_record_manager():
    return CassandraRecordManager(
        record_class=IntegerSequencedRecord,
        sequenced_item_class=SequencedItem,
    )


def construct_timestamp_sequenced_record_manager():
    return CassandraRecordManager(
        record_class=TimestampSequencedRecord,
        sequenced_item_class=SequencedItem,
    )


def construct_snapshot_record_manager():
    return CassandraRecordManager(
        record_class=SnapshotRecord,
        sequenced_item_class=SequencedItem,
    )


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
