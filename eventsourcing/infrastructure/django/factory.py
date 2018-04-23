from eventsourcing.infrastructure.django.manager import DjangoRecordManager
from eventsourcing.infrastructure.django.models import IntegerSequencedRecord, TimestampSequencedRecord, SnapshotRecord
from eventsourcing.infrastructure.factory import InfrastructureFactory


class DjangoInfrastructureFactory(InfrastructureFactory):
    record_manager_class = DjangoRecordManager
    integer_sequenced_record_class = IntegerSequencedRecord
    timestamp_sequenced_record_class = TimestampSequencedRecord
    snapshot_record_class = SnapshotRecord
