from abc import abstractmethod, ABCMeta
from six import with_metaclass
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import setup_cassandra_connection, \
    get_cassandra_setup_params, shutdown_cassandra_connection, CassandraStoredEventRepository
from eventsourcing.infrastructure.stored_events.rdbms import get_scoped_session_facade, SQLAlchemyStoredEventRepository


class EventSourcingApplication(with_metaclass(ABCMeta)):

    def __init__(self):
        self.stored_event_repo = self.create_stored_event_repo()
        self.event_store = self.create_event_store()
        self.persistence_subscriber = self.create_persistence_subscriber()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.persistence_subscriber.close()

    @abstractmethod
    def create_stored_event_repo(self):
        raise NotImplementedError()

    def create_event_store(self):
        return EventStore(stored_event_repo=self.stored_event_repo)

    def create_persistence_subscriber(self):
        return PersistenceSubscriber(event_store=self.event_store)


class EventSourcingWithSQLAlchemy(EventSourcingApplication):

    def __init__(self, db_session=None, db_uri=None):
        self.db_session = db_session if db_session is not None else self.create_db_session(db_uri)
        super(EventSourcingWithSQLAlchemy, self).__init__()

    @staticmethod
    def create_db_session(uri):
        return get_scoped_session_facade(uri)

    def create_stored_event_repo(self):
        return SQLAlchemyStoredEventRepository(db_session=self.db_session)


class EventSourcingWithCassandra(EventSourcingApplication):

    def __init__(self, hosts=('localhost',), consistency='QUORUM', default_keyspace='eventsourcing', port=9042,
                               protocol_version=2, username=None, password=None):
        self.setup_cassandra_connection(hosts, consistency, default_keyspace, port, protocol_version, username,
                                        password)
        super(EventSourcingWithCassandra, self).__init__()

    def setup_cassandra_connection(self, *args):
        setup_cassandra_connection(*get_cassandra_setup_params(*args))

    def create_stored_event_repo(self):
        return CassandraStoredEventRepository()

    def close(self):
        super(EventSourcingWithCassandra, self).close()
        shutdown_cassandra_connection()
