from eventsourcing.tests.stored_event_repository_tests.base_cassandra import CassandraRepoTestCase
from eventsourcing.tests.stored_event_repository_tests.base import StoredEventRepositoryTestCase, \
    OptimisticConcurrencyControlTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase
from eventsourcing.tests.base import notquick


class TestCassandraStoredEventRepository(CassandraRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass

@notquick()
class TestOptimisticConcurrencyControlWithCassandra(CassandraRepoTestCase, OptimisticConcurrencyControlTestCase):
    pass
