from eventsourcing.application.base import EventSourcingApplication
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import setup_cassandra_connection, \
    get_cassandra_setup_params, CassandraStoredEventRepository, DEFAULT_CASSANDRA_KEYSPACE, DEFAULT_CASSANDRA_HOSTS, \
    DEFAULT_CASSANDRA_CONSISTENCY_LEVEL, DEFAULT_CASSANDRA_PORT, DEFAULT_CASSANDRA_PROTOCOL_VERSION


class EventSourcingWithCassandra(EventSourcingApplication):

    def __init__(self, hosts=DEFAULT_CASSANDRA_HOSTS, consistency=DEFAULT_CASSANDRA_CONSISTENCY_LEVEL,
                 default_keyspace=DEFAULT_CASSANDRA_KEYSPACE, port=DEFAULT_CASSANDRA_PORT,
                 protocol_version=DEFAULT_CASSANDRA_PROTOCOL_VERSION, username=None, password=None, **kwargs):
        self.setup_cassandra_connection(hosts, consistency, default_keyspace, port, protocol_version, username,
                                        password)
        super(EventSourcingWithCassandra, self).__init__(**kwargs)

    @staticmethod
    def setup_cassandra_connection(*args):
        setup_cassandra_connection(*get_cassandra_setup_params(*args))

    def create_stored_event_repo(self, **kwargs):
        return CassandraStoredEventRepository(**kwargs)

    def close(self):
        super(EventSourcingWithCassandra, self).close()
        # shutdown_cassandra_connection()
