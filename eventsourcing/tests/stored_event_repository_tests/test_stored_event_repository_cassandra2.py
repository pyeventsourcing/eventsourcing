from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    OptimisticConcurrencyControlTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase, \
    notquick
from eventsourcing.tests.unit_test_cases_cassandra2 import Cassandra2Repo2TestCase


class TestCassandra2StoredEventRepository(Cassandra2Repo2TestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra2(Cassandra2Repo2TestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra2(Cassandra2Repo2TestCase, ThreadedStoredEventIteratorTestCase):
    pass

@notquick()
class TestOptimisticConcurrencyControlWithCassandra2(Cassandra2Repo2TestCase, OptimisticConcurrencyControlTestCase):
    pass
