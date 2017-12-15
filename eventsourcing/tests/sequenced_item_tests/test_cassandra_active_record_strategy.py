from eventsourcing.infrastructure.cassandra.models import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord

from eventsourcing.infrastructure.cassandra.strategy import CassandraRecordStrategy
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase, \
    WithActiveRecordStrategies


def construct_integer_sequenced_active_record_strategy():
    return CassandraRecordStrategy(
        active_record_class=IntegerSequencedRecord,
        sequenced_item_class=SequencedItem,
    )


def construct_timestamp_sequenced_active_record_strategy():
    return CassandraRecordStrategy(
        active_record_class=TimestampSequencedRecord,
        sequenced_item_class=SequencedItem,
    )


def construct_snapshot_active_record_strategy():
    return CassandraRecordStrategy(
        active_record_class=SnapshotRecord,
        sequenced_item_class=SequencedItem,
    )


class TestCassandraRecordStrategyWithIntegerSequences(CassandraDatastoreTestCase,
                                                      IntegerSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return construct_integer_sequenced_active_record_strategy()


class TestCassandraRecordStrategyWithTimestampSequences(CassandraDatastoreTestCase,
                                                        TimestampSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return construct_timestamp_sequenced_active_record_strategy()


class WithCassandraRecordStrategies(CassandraDatastoreTestCase, WithActiveRecordStrategies):
    def construct_entity_active_record_strategy(self):
        return construct_integer_sequenced_active_record_strategy()

    def construct_log_active_record_strategy(self):
        return construct_timestamp_sequenced_active_record_strategy()

    def construct_snapshot_active_record_strategy(self):
        return construct_snapshot_active_record_strategy()


class TestSimpleSequencedItemIteratorWithCassandra(WithCassandraRecordStrategies,
                                                   SimpleSequencedItemteratorTestCase):
    pass


class TestThreadedSequencedItemIteratorWithCassandra(WithCassandraRecordStrategies,
                                                     ThreadedSequencedItemIteratorTestCase):
    pass
