from eventsourcing.application.base import EventSourcingApplication
from eventsourcing.infrastructure.stored_events.cassandra_stored_events import setup_cassandra_connection, \
    get_cassandra_setup_params, shutdown_cassandra_connection, CassandraStoredEventRepository


DEFAULT_CASSANDRA_KEYSPACE = 'eventsourcing'


class EventSourcingWithCassandra(EventSourcingApplication):

    def __init__(self, hosts=('localhost',), consistency='QUORUM', default_keyspace=DEFAULT_CASSANDRA_KEYSPACE,
                 port=9042, protocol_version=2, username=None, password=None, **kwargs):
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
        shutdown_cassandra_connection()
