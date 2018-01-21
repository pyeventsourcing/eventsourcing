from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import IntegerSequencedItemTestCase, \
    SimpleSequencedItemteratorTestCase, ThreadedSequencedItemIteratorTestCase, TimestampSequencedItemTestCase, \
    WithRecordManagers


class TestCassandraRecordManagerWithIntegerSequences(CassandraDatastoreTestCase,
                                                     IntegerSequencedItemTestCase):
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
