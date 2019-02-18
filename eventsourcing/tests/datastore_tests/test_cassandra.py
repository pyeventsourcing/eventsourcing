from unittest.case import TestCase
from uuid import uuid4

from cassandra import InvalidRequest
from cassandra.cluster import NoHostAvailable
from cassandra.cqlengine import CQLEngineException

from eventsourcing.exceptions import DatasourceSettingsError
from eventsourcing.infrastructure.cassandra.factory import CassandraInfrastructureFactory
from eventsourcing.infrastructure.cassandra.records import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord
from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
from eventsourcing.infrastructure.datastore import DatastoreConnectionError, DatastoreTableError
from eventsourcing.tests.datastore_tests import base

DEFAULT_KEYSPACE_FOR_TESTING = 'eventsourcing_tests'


class CassandraDatastoreTestCase(base.AbstractDatastoreTestCase):
    """
    Uses the datastore object to set up connection to and tables in Cassandra.
    """
    infrastructure_factory_class = CassandraInfrastructureFactory

    def construct_datastore(self):
        return CassandraDatastore(
            settings=CassandraSettings(default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING),
            tables=(IntegerSequencedRecord, TimestampSequencedRecord, SnapshotRecord),
        )


class TestCassandraDatastore(CassandraDatastoreTestCase, base.DatastoreTestCase):
    def list_records(self):
        try:
            return list(IntegerSequencedRecord.objects.all())
        except (CQLEngineException, NoHostAvailable) as e:
            raise DatastoreConnectionError(e)
        except InvalidRequest as e:
            raise DatastoreTableError(e)

    def create_record(self):
        record = IntegerSequencedRecord(
            sequence_id=uuid4(),
            position=0,
            topic='topic',
            state='{}'
        )
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
            tables=(IntegerSequencedRecord,),
        )
        datastore.setup_connection()


class TestDatabaseSettingsError(TestCase):
    def test_consistency_level_error(self):
        datastore = CassandraDatastore(
            settings=CassandraSettings(
                default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING,
                consistency='invalid',
            ),
            tables=(IntegerSequencedRecord,),
        )

        with self.assertRaises(DatasourceSettingsError):
            datastore.setup_connection()
