from uuid import uuid4

from pynamodb.exceptions import PutError, ScanError

from eventsourcing.infrastructure.datastore import (
    DatastoreTableError,
)
from eventsourcing.infrastructure.dynamodb.datastore import (
    DynamoDbDatastore,
    DynamoDbSettings,
)
from eventsourcing.infrastructure.dynamodb.factory import \
    DynamoDbInfrastructureFactory
from eventsourcing.infrastructure.dynamodb.records import (
    IntegerSequencedRecord,
    SnapshotRecord,
    StoredEventRecord,
    TimestampSequencedRecord,
)
from eventsourcing.tests.datastore_tests import base


class DynamoDbDatastoreTestCase(base.AbstractDatastoreTestCase):
    """
    Uses the datastore object to set up tables in DynamoDB.
    """

    infrastructure_factory_class = DynamoDbInfrastructureFactory

    def construct_datastore(self):
        return DynamoDbDatastore(
            settings=DynamoDbSettings(wait_for_table=True),
            tables=(
                IntegerSequencedRecord,
                SnapshotRecord,
                StoredEventRecord,
                TimestampSequencedRecord,
            ),
        )


class TestDynamoDbDatastore(DynamoDbDatastoreTestCase, base.DatastoreTestCase):
    def list_records(self):
        records = []
        for table in self.datastore.tables:
            try:
                records.extend(table.scan())
            except ScanError as e:
                raise DatastoreTableError(e)
        return records

    def create_record(self):
        record = IntegerSequencedRecord(
            sequence_id=uuid4(), position=0, topic="topic", state=b"{}"
        )
        try:
            record.save()
        except PutError as e:
            raise DatastoreTableError(e)
        return record
