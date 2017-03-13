from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, CqlStoredEvent, \
    CqlIntegerSequencedItem, CqlTimeSequencedItem, CassandraIntegerSequencedItemRepository, \
    CassandraTimeSequencedItemRepository
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_repository_tests.base import AbstractStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, \
    ThreadedStoredEventIteratorTestCase, IntegerSequencedItemRepositoryTestCase, \
    TimeSequencedItemRepositoryTestCase


class CassandraRepoTestCase(CassandraDatastoreTestCase, AbstractStoredEventRepositoryTestCase):
    """
    Implements the sequenced_item_repo property, by
    providing a Cassandra stored event repository.
    """

    def construct_stored_event_repo(self):
        return CassandraStoredEventRepository(
            stored_event_table=CqlStoredEvent,
            always_write_entity_version=True,
            always_check_expected_version=True,
        )


class TestCassandraIntegerSequencedItemRepository(CassandraDatastoreTestCase, IntegerSequencedItemRepositoryTestCase):

    def construct_repo(self):
        return CassandraIntegerSequencedItemRepository(
            item_table=CqlIntegerSequencedItem,
        )


class TestCassandraTimeSequencedItemRepository(CassandraDatastoreTestCase, TimeSequencedItemRepositoryTestCase):

    def construct_repo(self):
        return CassandraTimeSequencedItemRepository(
            item_table=CqlTimeSequencedItem,
        )


class TestCassandraStoredEventRepository(CassandraRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass
