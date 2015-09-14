import os
from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.management import sync_table, create_keyspace_simple
import cassandra.cqlengine.connection
from six import string_types
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository, StoredEvent


class CqlStoredEvent(Model):
    stored_entity_id = columns.Text(partition_key=True)
    event_id = columns.TimeUUID(clustering_order='ASC', primary_key=True)
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
        return map(from_cql, cql_stored_events)

    def get_entity_events(self, stored_entity_id):
        cql_stored_events = CqlStoredEvent.objects(stored_entity_id=stored_entity_id).order_by('event_id')
        return map(from_cql, cql_stored_events)


def get_cassandra_setup_params(hosts=('localhost',), consistency='QUORUM', default_keyspace='eventsourcing', port=9042,
                               protocol_version=2, username=None, password=None):

    # Construct an "auth provider" object.
    if username and password:
        auth_provider = PlainTextAuthProvider(username, password)
    else:
        auth_provider = None

    # Resolve the consistency level to an object, if it's a string.
    if isinstance(consistency, string_types):
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
    create_cassandra_keyspace_and_tables(default_keyspace)


def create_cassandra_keyspace_and_tables(default_keyspace):
    os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'
    create_keyspace_simple(default_keyspace, replication_factor=1)
    sync_table(CqlStoredEvent)


def shutdown_cassandra_connection():
    if cassandra.cqlengine.connection.session:
        cassandra.cqlengine.connection.session.shutdown()
    if cassandra.cqlengine.connection.cluster:
        cassandra.cqlengine.connection.cluster.shutdown()
