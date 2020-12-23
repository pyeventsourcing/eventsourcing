from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.popo.manager import PopoRecordManager
from eventsourcing.infrastructure.popo.records import (
    IntegerSequencedRecord,
    SnapshotRecord,
)


class PopoInfrastructureFactory(InfrastructureFactory):
    record_manager_class = PopoRecordManager
    integer_sequenced_record_class = IntegerSequencedRecord
    snapshot_record_class = SnapshotRecord
