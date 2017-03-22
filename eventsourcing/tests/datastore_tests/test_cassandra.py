from unittest.case import TestCase

from cassandra import InvalidRequest
from cassandra.cluster import NoHostAvailable
from cassandra.cqlengine import CQLEngineException

from eventsourcing.exceptions import DatasourceSettingsError
from eventsourcing.infrastructure.cassandra.activerecords import CqlIntegerSequencedItem, CqlTimestampSequencedItem
from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.datastore import DatastoreConnectionError, DatastoreTableError
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase, DatastoreTestCase

DEFAULT_KEYSPACE_FOR_TESTING = 'eventsourcing_tests'


class CassandraDatastoreTestCase(AbstractDatastoreTestCase):
    """
    Uses the datastore object to set up connection to and tables in Cassandra.
    """

    def construct_datastore(self):
        return CassandraDatastore(
            settings=CassandraSettings(default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING),
            tables=(CqlIntegerSequencedItem, CqlTimestampSequencedItem),
        )


class TestCassandraDatastore(CassandraDatastoreTestCase, DatastoreTestCase):
    def list_records(self):
        try:
            return list(CqlIntegerSequencedItem.objects.all())
        except (CQLEngineException, NoHostAvailable) as e:
            raise DatastoreConnectionError(e)
        except InvalidRequest as e:
            raise DatastoreTableError(e)

    def create_record(self):
        record = CqlIntegerSequencedItem(s='entity1', p=0, t='topic', d='{}')
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
            tables=(CqlIntegerSequencedItem,),
        )
        datastore.setup_connection()


class TestDatabaseSettingsError(TestCase):
    def test_consistency_level_error(self):
        datastore = CassandraDatastore(
            settings=CassandraSettings(
                default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING,
                consistency='invalid',
            ),
            tables=(CqlIntegerSequencedItem,),
        )

        with self.assertRaises(DatasourceSettingsError):
            datastore.setup_connection()
