import os
from random import random
from time import sleep

import cassandra.cqlengine.connection
import six
from cassandra import ConsistencyLevel, AlreadyExists, DriverException
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.management import sync_table, create_keyspace_simple, drop_keyspace
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.query import LWTException

from eventsourcing.exceptions import ConcurrencyError, EntityVersionDoesNotExist
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository, ThreadedStoredEventIterator
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent, EntityVersion

DEFAULT_CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'eventsourcing')
DEFAULT_CASSANDRA_CONSISTENCY_LEVEL = os.getenv('CASSANDRA_CONSISTENCY_LEVEL', 'LOCAL_QUORUM')
DEFAULT_CASSANDRA_HOSTS = [h.strip() for h in os.getenv('CASSANDRA_HOSTS', 'localhost').split(',')]
DEFAULT_CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', 9042))
DEFAULT_CASSANDRA_PROTOCOL_VERSION = int(os.getenv('CASSANDRA_PROTOCOL_VERSION', 3))


class CqlEntityVersion(Model):
    """Stores the stored entity ID and entity version as a partition key."""

    __table_name__ = 'entity_versions'

    # Makes sure we can't write the same version twice,
    # helps to implement optimistic concurrency control.
    _if_not_exists = True

    # Entity-version identifier (a string).
    r = columns.Text(partition_key=True)

    # Stored event ID (normally a uuid1().hex).
    v = columns.Text()

    # Because models with one column break Cassandra driver 3.5.0.
    x = columns.Text(default='')


class CqlStoredEvent(Model):

    __table_name__ = 'stored_events'

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

    @property
    def iterator_class(self):
        return ThreadedStoredEventIterator

    def write_version_and_event(self, new_stored_event, new_version_number=None, max_retries=3, artificial_failure_rate=0):
        """
        Writes entity version if not exists, and then writes the stored event.
        """
        # Write the next version.
        stored_entity_id = new_stored_event.stored_entity_id
        new_entity_version = None
        if self.always_write_entity_version and new_version_number is not None:
            assert isinstance(new_version_number, six.integer_types)
            #  - uses the "if not exists" optimistic concurrency control feature
            #    of Cassandra, hence this operation is assumed to succeed only once
            new_entity_version_id = self.make_entity_version_id(stored_entity_id, new_version_number)
            new_entity_version = CqlEntityVersion(
                r=new_entity_version_id,
                v=new_stored_event.event_id,
            )
            try:
                new_entity_version.save()
            except LWTException as e:
                raise ConcurrencyError("Version {} of entity {} already exists: {}".format(new_entity_version, stored_entity_id, e))

        # Increased latency here causes increased contention.
        #  - used for testing concurrency exceptions
        if artificial_failure_rate:
            sleep(artificial_failure_rate)

        # Write the stored event into the database.
        try:
            retries = max_retries
            while True:
                try:
                    # Instantiate a Cassandra CQL engine object.
                    cql_stored_event = to_cql(new_stored_event)

                    # Optionally mimic an unreliable save() operation.
                    #  - used for testing retries
                    if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                        raise DriverException("Artificial failure")

                    # Save the event.
                    cql_stored_event.save()

                except DriverException:

                    if retries <= 0:
                        # Raise the error after retries exhausted.
                        raise
                    else:
                        # Otherwise retry.
                        retries -= 1
                        sleep(0.05 + 0.1 * random())
                else:
                    break

        except DriverException as event_write_error:
            # If we get here, we're in trouble because the version has been
            # written, but perhaps not the event, so the entity may be broken
            # because it might not be possible to get the entity with version
            # number high enough to pass the optimistic concurrency check
            # when storing subsequent events.

            # Back off for a little bit.
            sleep(0.1)
            try:
                # If the event actually exists, despite the exception, all is well.
                CqlStoredEvent.get(n=new_stored_event.stored_entity_id, v=new_stored_event.event_id)

            except CqlStoredEvent.DoesNotExist:
                # Otherwise, try harder to recover by removing the new version.
                if new_entity_version is not None:
                    retries = max_retries * 3
                    while True:
                        try:
                            # Optionally mimic an unreliable delete() operation.
                            #  - used for testing retries
                            if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                                raise DriverException("Artificial failure")

                            # Delete the new entity version.
                            new_entity_version.delete()

                        except DriverException as version_delete_error:
                            # It's not going very well, so maybe retry.
                            if retries <= 0:
                                # Raise when retries are exhausted.
                                raise Exception("Unable to delete version {} of entity {} after failing to write"
                                                "event: event write error {}: version delete error {}"
                                                .format(new_entity_version, stored_entity_id,
                                                        event_write_error, version_delete_error))
                            else:
                                # Otherwise retry.
                                retries -= 1
                                sleep(0.05 + 0.1 * random())
                        else:
                            # The entity version was deleted, all is well.
                            break
                raise event_write_error

    def get_entity_version(self, stored_entity_id, version_number):
        entity_version_id = self.make_entity_version_id(stored_entity_id, version_number)
        try:
            cql_entity_version = CqlEntityVersion.get(r=entity_version_id)
        except CqlEntityVersion.DoesNotExist:
            raise EntityVersionDoesNotExist()
        assert isinstance(cql_entity_version, CqlEntityVersion)
        return EntityVersion(
            entity_version_id=entity_version_id,
            event_id=cql_entity_version.v,
        )

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
        sync_table(CqlEntityVersion)


def drop_cassandra_keyspace(keyspace=DEFAULT_CASSANDRA_KEYSPACE):
    drop_keyspace(keyspace)


def shutdown_cassandra_connection():
    if cassandra.cqlengine.connection.session:
        cassandra.cqlengine.connection.session.shutdown()
    if cassandra.cqlengine.connection.cluster:
        cassandra.cqlengine.connection.cluster.shutdown()
