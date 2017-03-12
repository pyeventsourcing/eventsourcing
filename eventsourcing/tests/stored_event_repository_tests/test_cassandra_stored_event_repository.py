from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, CqlStoredEvent, \
    CqlIntegerSequencedItem, CqlTimeSequencedItem
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.stored_event_repository_tests.base import AbstractStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, \
    ThreadedStoredEventIteratorTestCase, IntegerSequencedEventRepositoryTestCase, \
    TimeSequencedEventRepositoryTestCase


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


class TestCassandraIntegerSequencedEventRepository(CassandraRepoTestCase, IntegerSequencedEventRepositoryTestCase):

    def construct_stored_event_repo(self):
        return CassandraStoredEventRepository(
            integer_sequenced_item_table=CqlIntegerSequencedItem,
        )


class TestCassandraTimeSequencedEventRepository(CassandraRepoTestCase, TimeSequencedEventRepositoryTestCase):

    def construct_stored_event_repo(self):
        return CassandraStoredEventRepository(
            time_sequenced_item_table=CqlTimeSequencedItem,
        )


class TestCassandraStoredEventRepository(CassandraRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass
