import os
from time import sleep

import cassandra.cqlengine
import six
from cassandra import AlreadyExists, ConsistencyLevel, InvalidRequest, OperationTimedOut
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.management import create_keyspace_simple, drop_keyspace, sync_table

from eventsourcing.infrastructure.datastore import DatastoreStrategy, DatastoreSettings

CASSANDRA_HOSTS = [h.strip() for h in os.getenv('CASSANDRA_HOSTS', 'localhost').split(',')]
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', 9042))
CASSANDRA_PROTOCOL_VERSION = int(os.getenv('CASSANDRA_PROTOCOL_VERSION', 3))
CASSANDRA_DEFAULT_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'eventsourcing')
CASSANDRA_CONSISTENCY_LEVEL = os.getenv('CASSANDRA_CONSISTENCY_LEVEL', 'LOCAL_QUORUM')
CASSANDRA_REPLICATION_FACTOR = os.getenv('CASSANDRA_REPLICATION_FACTOR', 1)


class CassandraDatastoreStrategy(DatastoreStrategy):

    def __init__(self, settings, tables):
        assert isinstance(settings, CassandraSettings), settings
        super(CassandraDatastoreStrategy, self).__init__(settings=settings, tables=tables)

    def setup_connection(self):
        setup_cassandra_connection(*get_cassandra_connection_params(self.settings))

    def drop_connection(self):
        shutdown_cassandra_connection()

    def setup_tables(self):
        create_cassandra_keyspace_and_tables(
            keyspace=self.settings.default_keyspace,
            replication_factor=self.settings.replication_factor,
            tables=self.tables,
        )

    def drop_tables(self):
        drop_cassandra_keyspace(
            keyspace=self.settings.default_keyspace,
        )


class CassandraSettings(DatastoreSettings):
    def __init__(
            self,
            hosts=CASSANDRA_HOSTS,
            port=CASSANDRA_PORT,
            protocol_version=CASSANDRA_PROTOCOL_VERSION,
            default_keyspace=CASSANDRA_DEFAULT_KEYSPACE,
            consistency=CASSANDRA_CONSISTENCY_LEVEL,
            replication_factor=CASSANDRA_REPLICATION_FACTOR,
            username=None,
            password=None
    ):
        self.hosts = hosts
        self.port = port
        self.protocol_version = protocol_version
        self.default_keyspace = default_keyspace
        self.consistency = consistency
        self.replication_factor = replication_factor
        self.username = username
        self.password = password


def get_cassandra_connection_params(settings):
    assert isinstance(settings, CassandraSettings), settings

    # Construct an "auth provider" object.
    if settings.username and settings.password:
        auth_provider = PlainTextAuthProvider(settings.username, settings.password)
    else:
        auth_provider = None

    # Resolve the consistency level to an object, if it's a string.
    if isinstance(settings.consistency, six.string_types):
        try:
            consistency = getattr(ConsistencyLevel, settings.consistency.upper())
        except AttributeError:
            msg = "Cassandra consistency level '{}' not found.".format(settings.consistency)
            raise Exception(msg)
    else:
        consistency = settings.consistency

    # Use the other settings directly.
    hosts = settings.hosts
    default_keyspace = settings.default_keyspace
    port = settings.port
    protocol_version = settings.protocol_version

    # Return a tuple of the args required by setup_cassandra_connection().
    return auth_provider, hosts, consistency, default_keyspace, port, protocol_version


def setup_cassandra_connection(auth_provider, hosts, consistency, default_keyspace, port, protocol_version):
    cassandra.cqlengine.connection.setup(
        hosts=hosts,
        consistency=consistency,
        default_keyspace=default_keyspace,
        port=port,
        auth_provider=auth_provider,
        protocol_version=protocol_version,
        lazy_connect=True,
        retry_connect=True,
    )


def create_cassandra_keyspace_and_tables(tables, keyspace=CASSANDRA_DEFAULT_KEYSPACE, replication_factor=1):
    # Avoid warnings about this variable not being set.
    os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'
    try:
        create_keyspace_simple(keyspace, replication_factor=replication_factor)
    except AlreadyExists:
        pass
    else:
        for table in tables:
            sync_table(table)


def drop_cassandra_keyspace(keyspace=CASSANDRA_DEFAULT_KEYSPACE):
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
