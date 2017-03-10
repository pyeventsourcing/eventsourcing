from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, CqlStoredEvent, \
    CqlIntegerSequencedEvent
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.stored_event_repository_tests.base import AbstractStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, \
    ThreadedStoredEventIteratorTestCase, IntegerSequencedEventRepositoryTestCase


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


class TestCassandraIntegerSequencedEventRepository(CassandraRepoTestCase, IntegerSequencedEventRepositoryTestCase):

    def construct_stored_event_repo(self):
        return CassandraStoredEventRepository(
            integer_sequenced_event_table=CqlIntegerSequencedEvent,
        )


class TestCassandraStoredEventRepository(CassandraRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass
