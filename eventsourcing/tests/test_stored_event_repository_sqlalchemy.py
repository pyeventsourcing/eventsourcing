from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    ConcurrentStoredEventRepositoryTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase
from eventsourcing.tests.unit_test_cases_sqlalchemy import SQLAlchemyRepoTestCase


class TestSQLAlchemyStoredEventRepository(SQLAlchemyRepoTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithSQLAlchemy(SQLAlchemyRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass


class TestConcurrentStoredEventRepositoryWithSQLAlchemy(SQLAlchemyRepoTestCase, ConcurrentStoredEventRepositoryTestCase):
    pass
