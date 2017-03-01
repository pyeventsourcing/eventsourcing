from eventsourcing.application.base import EventSourcingApplication
from eventsourcing.infrastructure.datastore.cassandra import CassandraDatastoreStrategy, CassandraSettings
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CassandraStoredEventRepository, \
    CqlStoredEvent


class EventSourcingWithCassandra(EventSourcingApplication):
    def __init__(self, settings=None, **kwargs):
        self.datastore = CassandraDatastoreStrategy(
            settings=settings or CassandraSettings(),
            tables=(CqlStoredEvent,)
        )
        self.datastore.setup_connection()
        super(EventSourcingWithCassandra, self).__init__(**kwargs)

    def create_stored_event_repo(self, **kwargs):
        return CassandraStoredEventRepository(**kwargs)

    def close(self):
        super(EventSourcingWithCassandra, self).close()
        # shutdown_cassandra_connection()
