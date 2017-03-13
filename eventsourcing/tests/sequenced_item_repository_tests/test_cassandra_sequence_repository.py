from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, CqlStoredEvent, \
    CassandraSequencedItemRepository, CassandraActiveRecordStrategy, CqlIntegerSequencedItem, CqlTimestampSequencedItem
from eventsourcing.infrastructure.transcoding import IntegerSequencedItem, TimeSequencedItem
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_repository_tests.base import AbstractStoredEventRepositoryTestCase, \
    IntegerSequencedItemRepositoryTestCase, SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, \
    ThreadedStoredEventIteratorTestCase, TimeSequencedItemRepositoryTestCase


class TestCassandraIntegerSequencedItemRepository(CassandraDatastoreTestCase, IntegerSequencedItemRepositoryTestCase):
    def construct_repo(self):
        return CassandraSequencedItemRepository(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlIntegerSequencedItem,
                sequenced_item_class=IntegerSequencedItem,
            )
        )


class TestCassandraTimeSequencedItemRepository(CassandraDatastoreTestCase, TimeSequencedItemRepositoryTestCase):
    def construct_repo(self):
        return CassandraSequencedItemRepository(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlTimestampSequencedItem,
                sequenced_item_class=TimeSequencedItem,
            )
        )


class CassandraIntegerSequencedRepoTestCase(CassandraDatastoreTestCase, AbstractStoredEventRepositoryTestCase):
    """
    Implements the sequenced_item_repo property, by
    providing a Cassandra stored event repository.
    """
    def construct_stored_event_repo(self):
        return CassandraSequencedItemRepository(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlIntegerSequencedItem,
                sequenced_item_class=IntegerSequencedItem,
            )
        )


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


class TestCassandraStoredEventRepository(CassandraRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithCassandra(CassandraRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithCassandra(CassandraRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass
