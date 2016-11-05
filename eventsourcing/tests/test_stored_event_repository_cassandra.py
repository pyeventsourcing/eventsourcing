from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    ConcurrentStoredEventRepositoryTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase, \
    notquick
from eventsourcing.tests.unit_test_cases_cassandra import CassandraRepoTestCase


class TestCassandraStoredEventRepository(CassandraRepoTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass

@notquick()
class TestConcurrentStoredEventRepositoryWithCassandra(CassandraRepoTestCase, ConcurrentStoredEventRepositoryTestCase):
    pass
