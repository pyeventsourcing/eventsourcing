import os

from cassandra import ConsistencyLevel, AlreadyExists
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.management import sync_table, create_keyspace_simple, drop_keyspace
import cassandra.cqlengine.connection
import six

from eventsourcing.infrastructure.stored_events.base import StoredEventRepository, ThreadedStoredEventIterator
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent

DEFAULT_CASSANDRA_KEYSPACE = 'eventsourcing'


class CqlStoredEvent(Model):
    __table_name__ = 'stored_events'
    # 'n' - stored entity ID (normally a string, with the entity type name at the start)
    n = columns.Text(partition_key=True)

    # 'v' - event ID (normally a UUID1)
    v = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # 't' - event topic (path to the event object class)
    t = columns.Text(required=True)

    # 'a' - event attributes (the entity object __dict__)
    a = columns.Text(required=True)


def to_cql(stored_event):
    assert isinstance(stored_event, StoredEvent)
    return CqlStoredEvent(
        n=stored_event.stored_entity_id,
        v=stored_event.event_id,
        t=stored_event.event_topic,
        a=stored_event.event_attrs
    )


def from_cql(cql_stored_event):
    assert isinstance(cql_stored_event, CqlStoredEvent), cql_stored_event
    return StoredEvent(
        stored_entity_id=cql_stored_event.n,
        event_id=cql_stored_event.v.hex,
        event_topic=cql_stored_event.t,
        event_attrs=cql_stored_event.a
    )


class CassandraStoredEventRepository(StoredEventRepository):

    serialize_with_uuid1 = True

    @property
    def iterator_class(self):
        return ThreadedStoredEventIterator

    def append(self, stored_event):
        cql_stored_event = to_cql(stored_event)
        cql_stored_event.save()

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True):
        query = CqlStoredEvent.objects.filter(n=stored_entity_id)

        if query_ascending:
            query = query.order_by('v')

        if after is not None:
            if query_ascending:
                query = query.filter(v__gt=after)
            else:
                query = query.filter(v__gte=after)
        if until is not None:
            if query_ascending:
                query = query.filter(v__lte=until)
            else:
                query = query.filter(v__lt=until)

        if limit is not None:
            query = query.limit(limit)

        events = self.map(from_cql, query)
        events = list(events)

        if results_ascending and not query_ascending:
            events.reverse()

        return events


def get_cassandra_setup_params(hosts=('localhost',), consistency='LOCAL_QUORUM',
                               default_keyspace=DEFAULT_CASSANDRA_KEYSPACE, port=9042,
                               protocol_version=3, username=None, password=None):

    # Construct an "auth provider" object.
    if username and password:
        auth_provider = PlainTextAuthProvider(username, password)
    else:
        auth_provider = None

    # Resolve the consistency level to an object, if it's a string.
    if isinstance(consistency, six.string_types):
        try:
            consistency = getattr(ConsistencyLevel, consistency.upper())
        except AttributeError:
            msg = "Cassandra consistency level '{}' not found.".format(consistency)
            raise Exception(msg)

    return auth_provider, hosts, consistency, default_keyspace, port, protocol_version


def setup_cassandra_connection(auth_provider, hosts, consistency, default_keyspace, port, protocol_version):
    cassandra.cqlengine.connection.setup(
        hosts=hosts,
        consistency=consistency,
        default_keyspace=default_keyspace,
        port=port,
        # auth_provider=auth_provider,
        protocol_version=protocol_version,
        # lazy_connect=True,
    )


def create_cassandra_keyspace_and_tables(keyspace=DEFAULT_CASSANDRA_KEYSPACE, replication_factor=1):
    # Avoid warnings about this variable not being set.
    os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'
    try:
        create_keyspace_simple(keyspace, replication_factor=replication_factor)
    except AlreadyExists:
        pass
    else:
        sync_table(CqlStoredEvent)


def drop_cassandra_keyspace(keyspace=DEFAULT_CASSANDRA_KEYSPACE):
    drop_keyspace(keyspace)


def shutdown_cassandra_connection():
    if cassandra.cqlengine.connection.session:
        cassandra.cqlengine.connection.session.shutdown()
    if cassandra.cqlengine.connection.cluster:
        cassandra.cqlengine.connection.cluster.shutdown()
