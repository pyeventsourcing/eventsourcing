import unittest
from tempfile import NamedTemporaryFile

from eventsourcing.tests.test_stored_events import BasicStoredEventRepositoryTestCase, SimpleStoredEventIteratorTestCase, \
    ThreadedStoredEventIteratorTestCase, ConcurrentStoredEventRepositoryTestCase
from eventsourcing.infrastructure.stored_events.sqlalchemy_stored_events import SQLAlchemyStoredEventRepository, \
    get_scoped_session_facade


class SQLAlchemyTestCase(unittest.TestCase):

    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            self.temp_file = NamedTemporaryFile('a')
            uri = 'sqlite:///' + self.temp_file.name
            scoped_session_facade = get_scoped_session_facade(uri)
            stored_event_repo = SQLAlchemyStoredEventRepository(scoped_session_facade)
            self._stored_event_repo = stored_event_repo
            return self._stored_event_repo

    def tearDown(self):
        # Unlink temporary file.
        if self.temp_file:
            self.temp_file.close()
        super(SQLAlchemyTestCase, self).tearDown()


class TestSQLAlchemyStoredEventRepository(SQLAlchemyTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithSQLAlchemy(SQLAlchemyTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithSQLAlchemy(SQLAlchemyTestCase, ThreadedStoredEventIteratorTestCase):
    pass


class TestConcurrentStoredEventRepositoryWithSQLAlchemy(SQLAlchemyTestCase, ConcurrentStoredEventRepositoryTestCase):
    pass
