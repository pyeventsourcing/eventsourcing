from eventsourcing.application.base import EventSourcingApplication
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CassandraStoredEventRepository
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import setup_cassandra_connection, \
    get_cassandra_connection_params


class EventSourcingWithCassandra(EventSourcingApplication):
    def __init__(self, connection_settings, **kwargs):
        self.setup_cassandra_connection(connection_settings)
        super(EventSourcingWithCassandra, self).__init__(**kwargs)

    @staticmethod
    def setup_cassandra_connection(settings):
        setup_cassandra_connection(*get_cassandra_connection_params(settings))

    def create_stored_event_repo(self, **kwargs):
        return CassandraStoredEventRepository(**kwargs)

    def close(self):
        super(EventSourcingWithCassandra, self).close()
        # shutdown_cassandra_connection()
