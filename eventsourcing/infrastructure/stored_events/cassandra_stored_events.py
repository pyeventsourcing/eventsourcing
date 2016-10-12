import os

from random import random
from time import sleep

from cassandra import ConsistencyLevel, AlreadyExists
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.management import sync_table, create_keyspace_simple, drop_keyspace
import cassandra.cqlengine.connection
import six
from cassandra.cqlengine.query import LWTException

from eventsourcing.exceptions import ConcurrencyError
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository, ThreadedStoredEventIterator
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent

DEFAULT_CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'eventsourcing')
DEFAULT_CASSANDRA_CONSISTENCY_LEVEL = os.getenv('CASSANDRA_CONSISTENCY_LEVEL', 'LOCAL_QUORUM')
DEFAULT_CASSANDRA_HOSTS = [h.strip() for h in os.getenv('CASSANDRA_HOSTS', 'localhost').split(',')]
DEFAULT_CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', 9042))
DEFAULT_CASSANDRA_PROTOCOL_VERSION = int(os.getenv('CASSANDRA_PROTOCOL_VERSION', 3))


class CqlStoredEntityVersion(Model):
    """Stores the stored entity ID and entity version as a partition key."""

    __table_name__ = 'entity_versions'

    # This makes sure we can't write the same version twice,
    # and helps to implement optimistic concurrency control.
    _if_not_exists = True

    # n = columns.Text(partition_key=True)
    #
    # # Version number (an integer)
    # i = columns.Text(primary_key=True)

    # Version number (an integer)
    r = columns.Text(partition_key=True)


class CqlStoredEvent(Model):

    __table_name__ = 'stored_events'

    # This makes sure we can't overwrite events.
    _if_not_exists = True

    # Stored entity ID (normally a string, with the entity type name at the start)
    n = columns.Text(partition_key=True)

    # Stored event ID (normally a UUID1)
    v = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # Stored event topic (path to the event object class)
    t = columns.Text(required=True)

    # Stored event attributes (the entity object __dict__)
    a = columns.Text(required=True)


def to_cql(stored_event):
    assert isinstance(stored_event, StoredEvent), stored_event
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

    def append(self, stored_event, expected_version=None, new_version=None):

        # Optimistic concurrency control.
        new_stored_version = None
        if new_version is not None:
            stored_entity_id = stored_event.stored_entity_id
            if expected_version is not None:
                # Read the expected version exists, raise concurrency exception if not.
                assert isinstance(expected_version, six.integer_types)
                expected_version_changed_id = self.make_version_changed_id(expected_version, stored_entity_id)
                try:
                    CqlStoredEntityVersion.get(r=expected_version_changed_id)
                except CqlStoredEntityVersion.DoesNotExist:
                    raise ConcurrencyError("Expected version '{}' of stored entity '{}' not found."
                                           "".format(expected_version, stored_entity_id))
            # Write the next version.
            #  - Uses "if not exists" feature of Cassandra, so
            #    this operation is assumed to succeed only once.
            #  - Raises concurrency exception if a "light weight
            #    transaction" exception is raised by Cassandra.
            new_stored_version_id = self.make_version_changed_id(new_version, stored_entity_id)
            new_stored_version = CqlStoredEntityVersion(r=new_stored_version_id)
            try:
                new_stored_version.save()
            except LWTException as e:
                raise ConcurrencyError("Couldn't update version because version already exists: {}".format(e))

        # Write the stored event into the database.
        try:
            cql_stored_event = to_cql(stored_event)
            cql_stored_event.save()
        except Exception as event_write_error:
            # If we get here, we're in trouble because the version has been
            # written, but perhaps not the event, so the entity may be broken
            # because it might not be possible to get the entity with version
            # number high enough to pass the optimistic concurrency check
            # when storing subsequent events.
            sleep(0.1)
            try:
                CqlStoredEvent.get(n=stored_event.stored_entity_id, v=stored_event.event_id)
            except CqlStoredEvent.DoesNotExist:
                # Try hard to recover the situation by removing the
                # new version, otherwise the entity will be stuck.
                if new_stored_version is not None:
                    retries = 5
                    while True:
                        try:
                            new_stored_version.delete()
                        except Exception as version_delete_error:
                            if retries == 0:
                                raise Exception("Unable to delete version after failing to write event: {}: {}"
                                                "".format(event_write_error, version_delete_error))
                            else:
                                retries -= 1
                                sleep(0.05 + 0.1 * random())
                        else:
                            break
                raise event_write_error
            else:
                # If the event actually exists, despite the exception, all is well.
                pass

    def make_version_changed_id(self, expected_version, stored_entity_id):
        return "VersionChanged::{}::version{}".format(stored_entity_id, expected_version)

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

        if results_ascending != query_ascending:
            events.reverse()

        return events


def get_cassandra_setup_params(hosts=DEFAULT_CASSANDRA_HOSTS, consistency=DEFAULT_CASSANDRA_CONSISTENCY_LEVEL,
                               default_keyspace=DEFAULT_CASSANDRA_KEYSPACE, port=DEFAULT_CASSANDRA_PORT,
                               protocol_version=DEFAULT_CASSANDRA_PROTOCOL_VERSION, username=None, password=None):

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
        auth_provider=auth_provider,
        # protocol_version=protocol_version,
        lazy_connect=True,
        retry_connect=True,
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
        sync_table(CqlStoredEntityVersion)


def drop_cassandra_keyspace(keyspace=DEFAULT_CASSANDRA_KEYSPACE):
    drop_keyspace(keyspace)


def shutdown_cassandra_connection():
    if cassandra.cqlengine.connection.session:
        cassandra.cqlengine.connection.session.shutdown()
    if cassandra.cqlengine.connection.cluster:
        cassandra.cqlengine.connection.cluster.shutdown()
