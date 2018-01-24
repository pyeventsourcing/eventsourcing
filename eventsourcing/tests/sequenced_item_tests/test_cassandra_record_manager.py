from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedRecordTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase, \
    WithRecordManagers


class TestCassandraRecordManagerWithIntegerSequences(CassandraDatastoreTestCase,
                                                     IntegerSequencedRecordTestCase):
    pass


class TestCassandraRecordManagerWithTimestampSequences(CassandraDatastoreTestCase,
                                                       TimestampSequencedItemTestCase):
    pass


class WithCassandraRecordManagers(CassandraDatastoreTestCase, WithRecordManagers):
    pass


class TestSimpleSequencedItemIteratorWithCassandra(WithCassandraRecordManagers,
                                                   SimpleSequencedItemteratorTestCase):
    pass


class TestThreadedSequencedItemIteratorWithCassandra(WithCassandraRecordManagers,
                                                     ThreadedSequencedItemIteratorTestCase):
    pass
