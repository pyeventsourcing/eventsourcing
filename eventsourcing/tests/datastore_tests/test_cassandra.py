from unittest.case import TestCase
from uuid import uuid1

from cassandra import InvalidRequest
from cassandra.cluster import NoHostAvailable
from cassandra.cqlengine import CQLEngineException

from eventsourcing.exceptions import DatasourceSettingsError
from eventsourcing.infrastructure.datastore.base import DatastoreConnectionError, DatastoreTableError
from eventsourcing.infrastructure.datastore.cassandraengine import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.storedevents.cassandrarepo import CqlEntityVersion, CqlStoredEvent, \
    CqlIntegerSequencedItem, CqlTimeSequencedItem
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase, DatastoreTestCase

DEFAULT_KEYSPACE_FOR_TESTING = 'eventsourcing_tests'


class CassandraDatastoreTestCase(AbstractDatastoreTestCase):
    """
    Uses the datastore object to set up connection to and tables in Cassandra.
    """

    def construct_datastore(self):
        return CassandraDatastore(
            settings=CassandraSettings(default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING),
            tables=(CqlStoredEvent, CqlEntityVersion, CqlIntegerSequencedItem, CqlTimeSequencedItem),
        )


class TestCassandraDatastore(CassandraDatastoreTestCase, DatastoreTestCase):

    def list_records(self):
        try:
            return list(CqlStoredEvent.objects.all())
        except (CQLEngineException, NoHostAvailable) as e:
            raise DatastoreConnectionError(e)
        except InvalidRequest as e:
            raise DatastoreTableError(e)

    def create_record(self):
        record = CqlStoredEvent(n='entity1', v=uuid1(), t='topic', a='{}')
        try:
            record.save()
        except (CQLEngineException, NoHostAvailable) as e:
            raise DatastoreConnectionError(e)
        except InvalidRequest as e:
            raise DatastoreTableError(e)
        return record


class TestPlainTextAuthProvider(TestCase):

    def test_plain_text_auth_provider(self):
        datastore = CassandraDatastore(
            settings=CassandraSettings(
                default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING,
                username='username',
                password='password',
            ),
            tables=(CqlStoredEvent, CqlEntityVersion),
        )
        datastore.setup_connection()


class TestDatabaseSettingsError(TestCase):

    def test_consistency_level_error(self):
        datastore = CassandraDatastore(
            settings=CassandraSettings(
                default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING,
                consistency='really great',
            ),
            tables=(CqlStoredEvent, CqlEntityVersion),
        )

        with self.assertRaises(DatasourceSettingsError):
            datastore.setup_connection()

