from eventsourcing.infrastructure.cassandra.manager import CassandraRecordManager
from eventsourcing.infrastructure.cassandra.records import IntegerSequencedRecord, SnapshotRecord, \
    TimestampSequencedRecord
from eventsourcing.infrastructure.factory import InfrastructureFactory


class CassandraInfrastructureFactory(InfrastructureFactory):
    record_manager_class = CassandraRecordManager
    integer_sequenced_record_class = IntegerSequencedRecord
    timestamp_sequenced_record_class = TimestampSequencedRecord
    snapshot_record_class = SnapshotRecord
