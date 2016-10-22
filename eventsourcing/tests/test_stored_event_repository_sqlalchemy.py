from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    ConcurrentStoredEventRepositoryTestCase, SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase
from eventsourcing.tests.unit_test_cases_sqlalchemy import SQLAlchemyTestCase


class TestSQLAlchemyStoredEventRepository(SQLAlchemyTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithSQLAlchemy(SQLAlchemyTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithSQLAlchemy(SQLAlchemyTestCase, ThreadedStoredEventIteratorTestCase):
    pass


class TestConcurrentStoredEventRepositoryWithSQLAlchemy(SQLAlchemyTestCase, ConcurrentStoredEventRepositoryTestCase):
    pass
