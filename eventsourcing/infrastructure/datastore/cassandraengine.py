import os

import cassandra.cqlengine
from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cqlengine.management import create_keyspace_simple, drop_keyspace, sync_table

from eventsourcing.exceptions import DatasourceSettingsError
from eventsourcing.infrastructure.datastore.base import DatastoreSettings, Datastore


class CassandraSettings(DatastoreSettings):
    CASSANDRA_HOSTS = [h.strip() for h in os.getenv('CASSANDRA_HOSTS', '127.0.0.1').split(',')]
    CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', 9042))
    CASSANDRA_PROTOCOL_VERSION = int(os.getenv('CASSANDRA_PROTOCOL_VERSION', 3))
    CASSANDRA_DEFAULT_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'eventsourcing')
    CASSANDRA_CONSISTENCY_LEVEL = os.getenv('CASSANDRA_CONSISTENCY_LEVEL', 'LOCAL_QUORUM')
    CASSANDRA_REPLICATION_FACTOR = os.getenv('CASSANDRA_REPLICATION_FACTOR', 1)

    def __init__(self, hosts=None, port=None, protocol_version=None, default_keyspace=None,
                 consistency=None, replication_factor=None, username=None, password=None):
        self.hosts = hosts or self.CASSANDRA_HOSTS
        self.port = port or self.CASSANDRA_PORT
        self.protocol_version = protocol_version or self.CASSANDRA_PROTOCOL_VERSION
        self.default_keyspace = default_keyspace or self.CASSANDRA_DEFAULT_KEYSPACE
        self.consistency = consistency or self.CASSANDRA_CONSISTENCY_LEVEL
        self.replication_factor = replication_factor or self.CASSANDRA_REPLICATION_FACTOR
        self.username = username
        self.password = password


class CassandraDatastore(Datastore):
    def setup_connection(self):
        assert isinstance(self.settings, CassandraSettings), self.settings

        # Optionally construct an "auth provider" object.
        if self.settings.username and self.settings.password:
            auth_provider = PlainTextAuthProvider(self.settings.username, self.settings.password)
        else:
            auth_provider = None

        # Resolve the consistency level to a driver object.
        try:
            consistency_level_name = self.settings.consistency.upper()
            consistency_level = ConsistencyLevel.name_to_value[consistency_level_name]
        except KeyError:
            msg = "Cassandra consistency level name '{}' not found.".format(self.settings.consistency)
            raise DatasourceSettingsError(msg)

        # Use the other self.settings directly.
        cassandra.cqlengine.connection.setup(
            hosts=self.settings.hosts,
            consistency=consistency_level,
            default_keyspace=self.settings.default_keyspace,
            port=self.settings.port,
            auth_provider=auth_provider,
            # protocol_version=self.settings.protocol_version,
            lazy_connect=True,
            retry_connect=True,
        )

    def drop_connection(self):
        if cassandra.cqlengine.connection.session:
            cassandra.cqlengine.connection.session.shutdown()
        if cassandra.cqlengine.connection.cluster:
            cassandra.cqlengine.connection.cluster.shutdown()

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

    def drop_tables(self):
        # Avoid warnings about this variable not being set.
        os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = '1'
        drop_keyspace(name=self.settings.default_keyspace)
