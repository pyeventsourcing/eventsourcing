from eventsourcing.tests.stored_event_repository_tests.base_cassandra import CassandraRepoTestCase
from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    OptimisticConcurrencyControlTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase, \
    notquick


class TestCassandraStoredEventRepository(CassandraRepoTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass

@notquick()
class TestOptimisticConcurrencyControlWithCassandra(CassandraRepoTestCase, OptimisticConcurrencyControlTestCase):
    pass
