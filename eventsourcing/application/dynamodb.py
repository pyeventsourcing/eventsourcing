from typing import Any, Optional

from eventsourcing.application.simple import (
    ApplicationWithConcreteInfrastructure,
)
from eventsourcing.infrastructure.dynamodb.factory import (
    DynamoDbInfrastructureFactory,
)
from eventsourcing.infrastructure.dynamodb.records import (
    SnapshotRecord,
    StoredEventRecord,
)


class DynamoDbApplication(ApplicationWithConcreteInfrastructure):
    infrastructure_factory_class = DynamoDbInfrastructureFactory
    stored_event_record_class = StoredEventRecord
    snapshot_record_class = SnapshotRecord

    def __init__(
        self,
        wait_for_table: Optional[bool] = False,
        **kwargs: Any
    ):
        """
        :param wait_for_table: wait for table creation (default: False)
        """
        self.wait_for_table = wait_for_table
        super().__init__(**kwargs)

    def construct_datastore(self) -> None:
        super().construct_datastore()
        assert self._datastore
