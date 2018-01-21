from eventsourcing.infrastructure.django.manager import DjangoRecordManager
from eventsourcing.infrastructure.django.models import IntegerSequencedRecord, TimestampSequencedRecord, SnapshotRecord
from eventsourcing.infrastructure.factory import InfrastructureFactory


class DjangoInfrastructureFactory(InfrastructureFactory):
    record_manager_class = DjangoRecordManager
    integer_sequenced_record_class = IntegerSequencedRecord
    timestamp_sequenced_record_class = TimestampSequencedRecord
    snapshot_record_class = SnapshotRecord

    def __init__(self, convert_position_float_to_decimal=False, *args, **kwargs):
        super(DjangoInfrastructureFactory, self).__init__(*args, **kwargs)
        self.convert_position_float_to_decimal = convert_position_float_to_decimal

    def construct_record_manager(self, **kwargs):
        return super(DjangoInfrastructureFactory, self).construct_record_manager(
            convert_position_float_to_decimal=self.convert_position_float_to_decimal, **kwargs)

