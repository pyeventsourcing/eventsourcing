from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events_sqlalchemy import SQLAlchemyStoredEventRepository, \
    get_scoped_session_facade


class EventSourcedApplication(object):

    def __init__(self, db_uri=None):
        self.db_session = self.create_db_session(db_uri)
        self.stored_event_repo = self.create_stored_event_repo()
        self.event_store = self.create_event_store()
        self.persistence_subscriber = self.create_persistence_subscriber()

    @staticmethod
    def create_db_session(uri):
        return get_scoped_session_facade(uri=uri)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.persistence_subscriber.close()

    def create_event_store(self):
        return EventStore(stored_event_repo=self.stored_event_repo)

    def create_stored_event_repo(self):
        return SQLAlchemyStoredEventRepository(db_session=self.db_session)

    def create_persistence_subscriber(self):
        return PersistenceSubscriber(event_store=self.event_store)
