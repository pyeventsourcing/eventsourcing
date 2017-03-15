from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraActiveRecordStrategy, \
    CqlIntegerSequencedItem, CqlTimestampSequencedItem
from eventsourcing.infrastructure.transcoding import SequencedItem
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import WithActiveRecordStrategies, IntegerSequencedItemTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase


def construct_integer_sequenced_active_record_strategy():
    return CassandraActiveRecordStrategy(
        active_record_class=CqlIntegerSequencedItem,
        sequenced_item_class=SequencedItem,
    )


def construct_timestamp_sequenced_active_record_strategy():
    return CassandraActiveRecordStrategy(
        active_record_class=CqlTimestampSequencedItem,
        sequenced_item_class=SequencedItem,
    )


class TestCassandraActiveRecordStrategyWithIntegerSequences(CassandraDatastoreTestCase,
                                                            IntegerSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return construct_integer_sequenced_active_record_strategy()


class TestCassandraActiveRecordStrategyWithTimestampSequences(CassandraDatastoreTestCase,
                                                              TimestampSequencedItemTestCase):
    def construct_active_record_strategy(self):
        return construct_timestamp_sequenced_active_record_strategy()


class CassandraActiveRecordStrategies(CassandraDatastoreTestCase, WithActiveRecordStrategies):
    def construct_integer_sequence_active_record_strategy(self):
        return construct_integer_sequenced_active_record_strategy()

    def construct_timestamp_sequence_active_record_strategy(self):
        return construct_timestamp_sequenced_active_record_strategy()



class TestSimpleStoredEventIteratorWithCassandra(CassandraActiveRecordStrategies,
                                                 SimpleSequencedItemteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraActiveRecordStrategies,
                                                   ThreadedSequencedItemIteratorTestCase):
    pass
