from eventsourcing.infrastructure.storedevents.sqlalchemyrepo import SQLAlchemyStoredEventRepository, \
    SqlStoredEvent
from eventsourcing.tests.datastore_tests.test_sqlalchemy import SQLAlchemyDatastoreTestCase
from eventsourcing.tests.stored_event_repository_tests.base import OptimisticConcurrencyControlTestCase, \
    SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, ThreadedStoredEventIteratorTestCase, \
    AbstractStoredEventRepositoryTestCase


class SQLAlchemyRepoTestCase(SQLAlchemyDatastoreTestCase, AbstractStoredEventRepositoryTestCase):

    def construct_stored_event_repo(self):
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


class TestOptimisticConcurrencyControlWithSQLAlchemy(SQLAlchemyRepoTestCase, OptimisticConcurrencyControlTestCase):
    use_named_temporary_file = True
