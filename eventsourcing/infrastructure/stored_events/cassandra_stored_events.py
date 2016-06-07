import os

from cassandra import ConsistencyLevel, AlreadyExists
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.management import sync_table, create_keyspace_simple
import cassandra.cqlengine.connection
import six

from eventsourcing.infrastructure.stored_events.base import StoredEventRepository, ThreadedStoredEventIterator
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent


class CqlStoredEvent(Model):
    __table_name__ = 'stored_events'
    n = columns.Text(partition_key=True)  # 'n' is for the stored entity ID
    v = columns.TimeUUID(clustering_order='DESC', primary_key=True)  # 'v' is for event ID
    t = columns.Text(required=True)  # 't' is for event topic
    a = columns.Text(required=True)  # 'a' is for event attributes


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

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_asc=False):
        query = CqlStoredEvent.objects.filter(n=stored_entity_id)
        if query_asc:
            query = query.order_by('v')
        if until is not None:
            query = query.filter(v__lte=until)
        if after is not None:
            query = query.filter(v__gt=after)
        if limit is not None:
            query = query.limit(limit)
        events = self.map(from_cql, query)
        if not query_asc:
            events = reversed(list(events))
        return events


def get_cassandra_setup_params(hosts=('localhost',), consistency='QUORUM', default_keyspace='eventsourcing', port=9042,
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
        default_keyspace=default_keyspace,
        consistency=consistency,
        # port=port,
        # auth_provider=auth_provider,
        # protocol_version=protocol_version,
        # lazy_connect=True,
    )


def create_cassandra_keyspace_and_tables(default_keyspace):
    os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'
    try:
        create_keyspace_simple(default_keyspace, replication_factor=1)
    except AlreadyExists:
        pass
    else:
        sync_table(CqlStoredEvent)


def shutdown_cassandra_connection():
    if cassandra.cqlengine.connection.session:
        cassandra.cqlengine.connection.session.shutdown()
    if cassandra.cqlengine.connection.cluster:
        cassandra.cqlengine.connection.cluster.shutdown()
