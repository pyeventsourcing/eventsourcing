import os

from cassandra import ConsistencyLevel, AlreadyExists
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.management import sync_table, create_keyspace_simple
import cassandra.cqlengine.connection
import six

from eventsourcing.infrastructure.stored_events.base import StoredEventRepository
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent


class CqlStoredEvent(Model):
    stored_entity_id = columns.Text(partition_key=True)
    event_id = columns.TimeUUID(clustering_order='DESC', primary_key=True)
    event_topic = columns.Text(index=True)
    event_attrs = columns.Text(required=True)


def to_cql(stored_event):
    assert isinstance(stored_event, StoredEvent)
    return CqlStoredEvent(
        event_id=stored_event.event_id,
        stored_entity_id=stored_event.stored_entity_id,
        event_attrs=stored_event.event_attrs,
        event_topic=stored_event.event_topic
    )


def from_cql(sql_stored_event):
    assert isinstance(sql_stored_event, CqlStoredEvent)
    return StoredEvent(
        event_id=sql_stored_event.event_id,
        stored_entity_id=sql_stored_event.stored_entity_id,
        event_attrs=sql_stored_event.event_attrs,
        event_topic=sql_stored_event.event_topic
    )


class CassandraStoredEventRepository(StoredEventRepository):

    serialize_with_uuid1 = True

    def append(self, stored_event):
        cql_stored_event = to_cql(stored_event)
        cql_stored_event.save()

    def __getitem__(self, event_id):
        cql_stored_event = CqlStoredEvent.objects.allow_filtering().filter(event_id=event_id).first()
        return from_cql(cql_stored_event)

    def __contains__(self, event_id):
        return bool(CqlStoredEvent.objects.allow_filtering().filter(event_id=event_id).limit(1).count())

    def get_topic_events(self, event_topic):
        cql_stored_events = CqlStoredEvent.objects(event_topic=event_topic)
        return self.map(from_cql, cql_stored_events)

    def get_entity_events(self, stored_entity_id, since=None, before=None, limit=None):
        query = CqlStoredEvent.objects.filter(stored_entity_id=stored_entity_id)
        query = query.order_by('event_id')
        if since is not None:
            query = query.filter(event_id__gt=since)
        if before is not None:
            query = query.filter(event_id__lt=before)
        if limit is not None:
            query = query.limit(limit)
        return self.map(from_cql, query)

    def get_most_recent_event(self, stored_entity_id):
        queryset = CqlStoredEvent.objects.filter(stored_entity_id=stored_entity_id)
        queryset = queryset.order_by('-event_id')
        queryset = queryset.limit(1)
        cql_stored_events = list(queryset)
        if len(cql_stored_events) == 1:
            return from_cql(cql_stored_events[0])
        elif len(cql_stored_events) == 0:
            return None
        else:
            raise Exception("Shouldn't have more than one object: {}".format(cql_stored_events))


def get_cassandra_setup_params(hosts=('localhost',), consistency='QUORUM', default_keyspace='eventsourcing', port=9042,
                               protocol_version=2, username=None, password=None):

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
        port=port,
        auth_provider=auth_provider,
        protocol_version=protocol_version,
        lazy_connect=True,
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
