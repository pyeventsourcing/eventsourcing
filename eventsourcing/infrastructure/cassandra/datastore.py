import os

import cassandra.cqlengine
from cassandra import ConsistencyLevel, OperationTimedOut
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import NoHostAvailable
from cassandra.cqlengine.management import create_keyspace_simple, drop_keyspace, sync_table

from eventsourcing.domain.model.decorators import retry
from eventsourcing.exceptions import DatasourceSettingsError
from eventsourcing.infrastructure.datastore import Datastore, DatastoreSettings

DEFAULT_HOSTS = '127.0.0.1'
DEFAULT_PORT = 9042
DEFAULT_PROTOCOL_VERSION = 3
DEFAULT_DEFAULT_KEYSPACE = 'eventsourcing'
DEFAULT_CONSISTENCY_LEVEL = 'LOCAL_QUORUM'
DEFAULT_REPLICATION_FACTOR = 1


class CassandraSettings(DatastoreSettings):
    HOSTS = [h.strip() for h in os.getenv('CASSANDRA_HOSTS', DEFAULT_HOSTS).split(',')]
    PORT = int(os.getenv('CASSANDRA_PORT', DEFAULT_PORT))
    PROTOCOL_VERSION = int(os.getenv('CASSANDRA_PROTOCOL_VERSION', DEFAULT_PROTOCOL_VERSION))
    DEFAULT_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', DEFAULT_DEFAULT_KEYSPACE)
    CONSISTENCY_LEVEL = os.getenv('CASSANDRA_CONSISTENCY_LEVEL', DEFAULT_CONSISTENCY_LEVEL)
    REPLICATION_FACTOR = os.getenv('CASSANDRA_REPLICATION_FACTOR', DEFAULT_REPLICATION_FACTOR)

    def __init__(self, hosts=None, port=None, protocol_version=None, default_keyspace=None,
                 consistency=None, replication_factor=None, username=None, password=None):
        self.hosts = hosts or self.HOSTS
        self.port = port or self.PORT
        self.protocol_version = protocol_version or self.PROTOCOL_VERSION
        self.default_keyspace = default_keyspace or self.DEFAULT_KEYSPACE
        self.consistency = consistency or self.CONSISTENCY_LEVEL
        self.replication_factor = replication_factor or self.REPLICATION_FACTOR
        self.username = username
        self.password = password


class CassandraDatastore(Datastore):
    def __init__(self, tables, *args, **kwargs):
        super(CassandraDatastore, self).__init__(*args, **kwargs)
        assert isinstance(tables, tuple), tables
        self.tables = tables

    def setup_connection(self):
        assert isinstance(self.settings, CassandraSettings), self.settings

        # Optionally construct an "auth provider" object.
        if self.settings.username and self.settings.password:
            auth_provider = PlainTextAuthProvider(
                username=self.settings.username,
                password=self.settings.password
            )
        else:
            auth_provider = None

        # Resolve the consistency level to a driver object.
        try:
            consistency_level_name = self.settings.consistency.upper()
            consistency_level = ConsistencyLevel.name_to_value[consistency_level_name]
        except KeyError:
            msg = ("Cassandra consistency level name '{}' not found."
                   "".format(self.settings.consistency))
            raise DatasourceSettingsError(msg)

        # Use the other self.settings directly.
        cassandra.cqlengine.connection.setup(
            hosts=self.settings.hosts,
            consistency=consistency_level,
            default_keyspace=self.settings.default_keyspace,
            port=self.settings.port,
            auth_provider=auth_provider,
            protocol_version=self.settings.protocol_version,
            lazy_connect=True,
            retry_connect=True,
        )

    def close_connection(self):
        if cassandra.cqlengine.connection.session:
            cassandra.cqlengine.connection.session.shutdown()
        if cassandra.cqlengine.connection.cluster:
            cassandra.cqlengine.connection.cluster.shutdown()

    @retry((NoHostAvailable, OperationTimedOut), max_attempts=10, wait=0.5)
    def setup_tables(self):
        # Avoid warnings about this variable not being set.
        os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'

        # Attempt to create the keyspace.
        create_keyspace_simple(
            name=self.settings.default_keyspace,
            replication_factor=self.settings.replication_factor,
        )
        for table in self.tables:
            sync_table(table)

    @retry(NoHostAvailable, max_attempts=10, wait=0.5)
    def drop_tables(self):
        drop_keyspace(name=self.settings.default_keyspace)

    def drop_table(self, *_):
        self.drop_tables()

    @retry(NoHostAvailable, max_attempts=10, wait=0.5)
    def truncate_tables(self):
        for table in self.tables:
            remaining_objects = table.objects.all().limit(10)
            while remaining_objects:
                for obj in remaining_objects:
                    obj.delete()
                remaining_objects = table.objects.all().limit(10)
