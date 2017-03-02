from eventsourcing.tests.stored_event_repository_tests.base import OptimisticConcurrencyControlTestCase, \
    SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, ThreadedStoredEventIteratorTestCase
from eventsourcing.tests.stored_event_repository_tests.base_sqlalchemy import SQLAlchemyRepoTestCase


class TestSQLAlchemyStoredEventRepository(SQLAlchemyRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass


class TestOptimisticConcurrencyControlWithSQLAlchemy(SQLAlchemyRepoTestCase, OptimisticConcurrencyControlTestCase):
    pass
