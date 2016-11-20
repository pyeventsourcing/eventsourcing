from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    OptimisticConcurrencyControlTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase, \
    notquick
from eventsourcing.tests.unit_test_cases_cassandraa import CassandraRepoTestCase


class TestCassandraStoredEventRepository(CassandraRepoTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass

@notquick()
class TestOptimisticConcurrencyControlWithCassandra(CassandraRepoTestCase, OptimisticConcurrencyControlTestCase):
    pass
