from typing import Any

from eventsourcing.infrastructure.dynamodb.datastore import (
    DynamoDbDatastore,
    DynamoDbSettings,
)
from eventsourcing.infrastructure.dynamodb.manager import DynamoDbRecordManager
from eventsourcing.infrastructure.dynamodb.records import (
    IntegerSequencedRecord,
    SnapshotRecord,
    StoredEventRecord,
    TimestampSequencedRecord,
)
from eventsourcing.infrastructure.factory import InfrastructureFactory


class DynamoDbInfrastructureFactory(InfrastructureFactory):
    """
    Infrastructure factory for DynamoDB infrastructure.
    """

    record_manager_class = DynamoDbRecordManager
    integer_sequenced_record_class = IntegerSequencedRecord
    timestamp_sequenced_record_class = TimestampSequencedRecord
    snapshot_record_class = SnapshotRecord

    def __init__(
        self,
        *args: Any,
        **kwargs: Any
    ):
        self.wait_for_table = kwargs.pop('wait_for_table', False)
        super().__init__(*args, **kwargs)

    def construct_datastore(self):
        return DynamoDbDatastore(
            settings=DynamoDbSettings(wait_for_table=self.wait_for_table),
            tables=(
                IntegerSequencedRecord,
                SnapshotRecord,
                StoredEventRecord,
                TimestampSequencedRecord,
            ),
        )
