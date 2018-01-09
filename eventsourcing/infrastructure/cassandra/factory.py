from eventsourcing.infrastructure.cassandra.records import IntegerSequencedRecord, TimestampSequencedRecord, \
    SnapshotRecord
from eventsourcing.infrastructure.cassandra.manager import CassandraRecordManager
from eventsourcing.infrastructure.sequenceditem import SequencedItem


def construct_integer_sequenced_record_manager():
    return CassandraRecordManager(
        record_class=IntegerSequencedRecord,
        sequenced_item_class=SequencedItem,
    )


def construct_timestamp_sequenced_record_manager():
    return CassandraRecordManager(
        record_class=TimestampSequencedRecord,
        sequenced_item_class=SequencedItem,
    )


def construct_snapshot_record_manager():
    return CassandraRecordManager(
        record_class=SnapshotRecord,
        sequenced_item_class=SequencedItem,
    )
