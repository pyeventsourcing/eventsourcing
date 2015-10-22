from eventsourcing.infrastructure.stored_events.rdbms import SQLAlchemyStoredEventRepository, \
    get_scoped_session_facade
from eventsourcingtests.test_stored_events import StoredEventRepositoryTestCase


class TestSQLAlchemyStoredEventRepository(StoredEventRepositoryTestCase):

    def test(self):
        stored_event_repo = SQLAlchemyStoredEventRepository(get_scoped_session_facade('sqlite:///:memory:'))
        self.assertStoredEventRepositoryImplementation(stored_event_repo)
