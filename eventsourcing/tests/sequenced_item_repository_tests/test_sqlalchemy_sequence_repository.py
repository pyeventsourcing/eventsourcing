from eventsourcing.infrastructure.storedevents.sqlalchemyrepo import SQLAlchemyActiveRecordStrategy, \
    SQLAlchemySequencedItemRepository, SQLAlchemyStoredEventRepository, SqlIntegerSequencedItem, SqlStoredEvent, \
    SqlTimestampSequencedItem
from eventsourcing.infrastructure.transcoding import SequencedItem
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.tests.sequenced_item_repository_tests.base import CombinedSequencedItemRepositoryTestCase, \
    IntegerSequencedItemRepositoryTestCase, SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, \
    ThreadedStoredEventIteratorTestCase, TimeSequencedItemRepositoryTestCase


class TestSQLAlchemyIntegerSequencedItemRepository(SQLAlchemyDatastoreTestCase,
                                                   IntegerSequencedItemRepositoryTestCase):
    def construct_repo(self):
        return SQLAlchemySequencedItemRepository(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                active_record_class=SqlIntegerSequencedItem,
                sequenced_item_class=SequencedItem,
                datastore=self.datastore,
            ),
        )


class TestSQLAlchemyTimeSequencedItemRepository(SQLAlchemyDatastoreTestCase, TimeSequencedItemRepositoryTestCase):
    def construct_repo(self):
        return SQLAlchemySequencedItemRepository(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                active_record_class=SqlTimestampSequencedItem,
                sequenced_item_class=SequencedItem,
                datastore=self.datastore,
            ),
        )


class SQLAlchemyRepoTestCase(SQLAlchemyDatastoreTestCase, CombinedSequencedItemRepositoryTestCase):
    def construct_integer_sequenced_item_repository(self):
        """
        Constructs a SQLAlchemy stored event repository.
        """
        return SQLAlchemyStoredEventRepository(
            datastore=self.datastore,
            stored_event_table=SqlStoredEvent,
            always_check_expected_version=True,
            always_write_entity_version=True,
        )


class TestSQLAlchemyStoredEventRepository(SQLAlchemyRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, ThreadedStoredEventIteratorTestCase):
    use_named_temporary_file = True
