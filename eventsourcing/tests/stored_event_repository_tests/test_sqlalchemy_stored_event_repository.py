from eventsourcing.tests.stored_event_repository_tests.base_sqlalchemy import SQLAlchemyRepoTestCase
from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    OptimisticConcurrencyControlTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase


class TestSQLAlchemyStoredEventRepository(SQLAlchemyRepoTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass


class TestOptimisticConcurrencyControlWithSQLAlchemy(SQLAlchemyRepoTestCase, OptimisticConcurrencyControlTestCase):
    pass
