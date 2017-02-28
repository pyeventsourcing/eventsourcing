import os
from random import random
from time import sleep

import cassandra.cqlengine.connection
import six
from cassandra import AlreadyExists, ConsistencyLevel, DriverException, InvalidRequest, OperationTimedOut
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine import ValidationError
from cassandra.cqlengine.management import create_keyspace_simple, drop_keyspace, sync_table
from cassandra.cqlengine.models import Model, columns
from cassandra.cqlengine.query import LWTException

from eventsourcing.exceptions import ConcurrencyError, EntityVersionDoesNotExist
from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository
from eventsourcing.infrastructure.stored_event_repos.threaded_iterator import ThreadedStoredEventIterator

DEFAULT_CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'eventsourcing')
DEFAULT_CASSANDRA_CONSISTENCY_LEVEL = os.getenv('CASSANDRA_CONSISTENCY_LEVEL', 'LOCAL_QUORUM')
DEFAULT_CASSANDRA_HOSTS = [h.strip() for h in os.getenv('CASSANDRA_HOSTS', 'localhost').split(',')]
DEFAULT_CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', 9042))
DEFAULT_CASSANDRA_PROTOCOL_VERSION = int(os.getenv('CASSANDRA_PROTOCOL_VERSION', 3))


class CqlEntityVersion(Model):
    """Stores the stored entity ID and entity version as a partition key."""

    __table_name__ = 'entity_versions'

    # Aggregate ID (normally a string, often a UUID, perhaps with the entity type name at the start).
    n = columns.Text(partition_key=True)

    # Stored event ID (normally a UUID1).
    i = columns.TimeUUID(clustering_order='DESC', primary_key=True)

    # Stored entity version.
    v = columns.BigInt()


class CqlStoredEvent(Model):
    __table_name__ = 'stored_events'

    # Makes sure we can't write the same version twice,
    # helps to implement optimistic concurrency control.
    _if_not_exists = True

    # Aggregate ID (normally a string, often a UUID, perhaps with the entity type name at the start).
    n = columns.Text(partition_key=True)

    # Aggregate version.
    v = columns.BigInt(clustering_order='DESC', primary_key=True)

    # Stored event ID (normally a UUID1).
    i = columns.TimeUUID()

    # Stored event topic (path to the event object class).
    t = columns.Text(required=True)

    # Stored event attributes (the entity object __dict__).
    a = columns.Text(required=True)


class Cassandra2StoredEventRepository(AbstractStoredEventRepository):
    @property
    def iterator_class(self):
        return ThreadedStoredEventIterator

    def write_version_and_event(self, new_stored_event, new_version_number=0, max_retries=3,
                                artificial_failure_rate=0):
        """
        Writes the stored event with version number.
        """
        # Write the next version.
        stored_entity_id = new_stored_event.stored_entity_id
        new_entity_version = None
        # Write the stored event into the database.
        try:
            retries = max_retries
            while True:
                try:

                    if new_version_number is None:
                        try:
                            cql_stored_event = CqlStoredEvent.objects.filter(n=stored_entity_id).limit(1).get()
                        except CqlStoredEvent.DoesNotExist:
                            new_version_number = 0
                        else:
                            new_version_number = cql_stored_event.v + 1

                    # Instantiate a Cassandra CQL engine object.
                    cql_stored_event = self.to_cql(new_stored_event, new_version_number)

                    # Optionally mimic an unreliable save() operation.
                    #  - used for testing retries
                    if artificial_failure_rate and (random() > 1 - artificial_failure_rate):
                        raise DriverException("Artificial failure")

                    # Save the event.
                    cql_stored_event.save()

                    if new_version_number is not None:
                        # Save the version number with the event ID (UUID1).
                        cql_entity_version = CqlEntityVersion(
                            n=stored_entity_id,
                            i=new_stored_event.event_id,
                            v=new_version_number
                        )
                        cql_entity_version.save()

                except DriverException as e:

                    if retries <= 0:
                        # Raise the error after retries exhausted.
                        raise
                    else:
                        # Otherwise retry.
                        retries -= 1
                        sleep(0.05 + 0.1 * random())

                except LWTException as e:
                    raise ConcurrencyError(
                        "Version {} of entity {} already exists: {}".format(new_entity_version, stored_entity_id, e))
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
                CqlStoredEvent.get(n=new_stored_event.stored_entity_id, v=new_version_number)

            except InvalidRequest:
                raise event_write_error
            except ValidationError:
                raise event_write_error
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
        try:
            CqlStoredEvent.get(n=stored_entity_id, v=version_number)
        except CqlEntityVersion.DoesNotExist:
            raise EntityVersionDoesNotExist()

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True):

        if limit is not None and limit < 1:
            return []

        query = CqlStoredEvent.objects.filter(n=stored_entity_id)

        if query_ascending:
            query = query.order_by('v')

        if after is not None:
            if query_ascending:
                try:
                    after_version = CqlEntityVersion.objects.order_by('i').limit(1).get(n=stored_entity_id,
                                                                                        i__gte=after).v
                except CqlEntityVersion.DoesNotExist:
                    pass
                else:
                    query = query.filter(v__gt=after_version)
            else:
                after_version = CqlEntityVersion.objects.limit(1).get(n=stored_entity_id, i__gte=after).v
                query = query.filter(v__gte=after_version)
        if until is not None:
            try:
                until_version = CqlEntityVersion.objects.limit(1).get(n=stored_entity_id, i__lte=until).v
            except CqlEntityVersion.DoesNotExist:
                pass
            else:
                if query_ascending:
                    query = query.filter(v__lte=until_version)
                else:
                    query = query.filter(v__lt=until_version)

        if limit is not None:
            query = query.limit(limit)

        events = self.map(self.from_cql, query)
        events = list(events)

        if results_ascending != query_ascending:
            events.reverse()

        return events

    def to_cql(self, stored_event, new_version_number):
        assert isinstance(stored_event, self.stored_event_class), stored_event
        return CqlStoredEvent(
            n=stored_event.stored_entity_id,
            v=new_version_number,
            i=stored_event.event_id,
            t=stored_event.event_topic,
            a=stored_event.event_attrs
        )

    def from_cql(self, cql_stored_event):
        assert isinstance(cql_stored_event, CqlStoredEvent), cql_stored_event
        return self.stored_event_class(
            stored_entity_id=cql_stored_event.n,
            event_id=cql_stored_event.i.hex,
            event_topic=cql_stored_event.t,
            event_attrs=cql_stored_event.a
        )


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


def create_cassandra2_keyspace_and_tables(keyspace=DEFAULT_CASSANDRA_KEYSPACE, replication_factor=1):
    # Avoid warnings about this variable not being set.
    os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'
    try:
        create_keyspace_simple(keyspace, replication_factor=replication_factor)
    except AlreadyExists:
        pass
    else:
        sync_table(CqlStoredEvent)
        sync_table(CqlEntityVersion)


def drop_cassandra2_keyspace(keyspace=DEFAULT_CASSANDRA_KEYSPACE):
    max_retries = 3
    tried = 0
    while True:
        try:
            drop_keyspace(keyspace)
            break
        except InvalidRequest:
            break
        except OperationTimedOut:
            tried += 1
            if tried <= max_retries:
                sleep(0.5)
                continue
            else:
                raise


def shutdown_cassandra_connection():
    if cassandra.cqlengine.connection.session:
        cassandra.cqlengine.connection.session.shutdown()
    if cassandra.cqlengine.connection.cluster:
        cassandra.cqlengine.connection.cluster.shutdown()
