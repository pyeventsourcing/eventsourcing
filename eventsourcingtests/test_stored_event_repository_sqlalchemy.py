from eventsourcing.infrastructure.stored_events.sqlalchemy_stored_events import SQLAlchemyStoredEventRepository, \
    get_scoped_session_facade
from eventsourcingtests.test_stored_events import StoredEventRepositoryTestCase


class TestSQLAlchemyStoredEventRepository(StoredEventRepositoryTestCase):

    def test_stored_events_in_sqlalchemy(self):
        stored_event_repo = SQLAlchemyStoredEventRepository(get_scoped_session_facade('sqlite:///:memory:'))
        self.checkStoredEventRepository(stored_event_repo)
