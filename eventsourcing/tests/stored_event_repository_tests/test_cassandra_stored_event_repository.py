from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, CqlStoredEvent
from eventsourcing.tests.base import notquick
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.stored_event_repository_tests.base import AbstractStoredEventRepositoryTestCase, \
    OptimisticConcurrencyControlTestCase, SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, \
    ThreadedStoredEventIteratorTestCase


class CassandraRepoTestCase(CassandraDatastoreTestCase, AbstractStoredEventRepositoryTestCase):
    """
    Implements the stored_event_repo property, by
    providing a Cassandra stored event repository.
    """

    def construct_stored_event_repo(self):
        return CassandraStoredEventRepository(
            stored_event_table=CqlStoredEvent,
            always_write_entity_version=True,
            always_check_expected_version=True,
        )


class TestCassandraStoredEventRepository(CassandraRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass


@notquick()
class TestOptimisticConcurrencyControlWithCassandra(CassandraRepoTestCase, OptimisticConcurrencyControlTestCase):
    pass
