from eventsourcing.application.base import EventSourcingApplication
from eventsourcing.infrastructure.stored_events.sqlalchemy_stored_events import \
    get_scoped_session_facade, SQLAlchemyStoredEventRepository


class EventSourcingWithSQLAlchemy(EventSourcingApplication):

    def __init__(self, db_session=None, db_uri=None, **kwargs):
        self.db_uri = db_uri
        self.db_session = db_session if (db_session is not None) else self.create_db_session(db_uri)
        super(EventSourcingWithSQLAlchemy, self).__init__(**kwargs)

    @staticmethod
    def create_db_session(uri):
        return get_scoped_session_facade(uri)

    def create_stored_event_repo(self, **kwargs):
        return SQLAlchemyStoredEventRepository(db_session=self.db_session, **kwargs)

    def close(self):
        super(EventSourcingWithSQLAlchemy, self).close()
        self.db_session.close()
