from eventsourcing.tests.datastore_tests.test_cassandra import (
    CassandraDatastoreTestCase,
)
from eventsourcing.tests.sequenced_item_tests import base


class TestCassandraRecordManagerWithTimestampSequences(
    CassandraDatastoreTestCase, base.TimestampSequencedItemTestCase
):
    pass


class TestCassandraRecordManagerWithIntegerSequences(
    CassandraDatastoreTestCase, base.IntegerSequencedRecordTestCase
):
    pass


class WithCassandraRecordManagers(CassandraDatastoreTestCase, base.WithRecordManagers):
    pass


class TestSequencedItemIteratorWithCassandra(
    WithCassandraRecordManagers, base.SequencedItemIteratorTestCase
):
    pass


class TestThreadedSequencedItemIteratorWithCassandra(
    WithCassandraRecordManagers, base.ThreadedSequencedItemIteratorTestCase
):
    pass
