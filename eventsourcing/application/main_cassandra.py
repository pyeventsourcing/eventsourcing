from .main import EventSourcingApplication
from eventsourcing.infrastructure.stored_events.cassandra_stored_events \
    import setup_cassandra_connection, \
    get_cassandra_setup_params, shutdown_cassandra_connection, \
    CassandraStoredEventRepository


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