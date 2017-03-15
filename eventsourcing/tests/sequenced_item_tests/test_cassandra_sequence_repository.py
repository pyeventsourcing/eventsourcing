from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, CqlStoredEvent, \
    CassandraSequencedItemRepository, CassandraActiveRecordStrategy, CqlIntegerSequencedItem, CqlTimestampSequencedItem
from eventsourcing.infrastructure.transcoding import SequencedItem
from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.base import CombinedSequencedItemRepositoryTestCase, \
    IntegerSequencedItemRepositoryTestCase, SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, \
    ThreadedStoredEventIteratorTestCase, TimeSequencedItemRepositoryTestCase


class TestCassandraIntegerSequencedItemRepository(CassandraDatastoreTestCase, IntegerSequencedItemRepositoryTestCase):
    def construct_repo(self):
        return CassandraSequencedItemRepository(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlIntegerSequencedItem,
                sequenced_item_class=SequencedItem,
            )
        )


class TestCassandraTimeSequencedItemRepository(CassandraDatastoreTestCase, TimeSequencedItemRepositoryTestCase):
    def construct_repo(self):
        return CassandraSequencedItemRepository(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlTimestampSequencedItem,
                sequenced_item_class=SequencedItem,
            )
        )


class CassandraIntegerSequencedRepoTestCase(CassandraDatastoreTestCase, CombinedSequencedItemRepositoryTestCase):
    def construct_integer_sequenced_item_repository(self):
        return CassandraSequencedItemRepository(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlIntegerSequencedItem,
                sequenced_item_class=SequencedItem,
            )
        )


class CassandraTimestampSequencedRepoTestCase(CassandraDatastoreTestCase, CombinedSequencedItemRepositoryTestCase):
    def construct_timestamp_sequenced_item_repository(self):
        return CassandraSequencedItemRepository(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlTimestampSequencedItem,
                sequenced_item_class=SequencedItem,
            )
        )


class CassandraRepoTestCase(CassandraDatastoreTestCase, CombinedSequencedItemRepositoryTestCase):
    """
    Implements the integer_sequenced_item_repository property, by
    providing a Cassandra stored event repository.
    """

    def construct_integer_sequenced_item_repository(self):
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
