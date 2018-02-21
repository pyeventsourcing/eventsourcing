from eventsourcing.infrastructure.django.manager import DjangoRecordManager
from eventsourcing.infrastructure.django.models import (
    StoredEventRecord,
    IntegerSequencedRecord,
    TimestampSequencedRecord,
    SnapshotRecord
)
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


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


def construct_django_eventstore(sequenced_item_class=None,
                                sequence_id_attr_name=None,
                                position_attr_name=None,
                                json_encoder_class=None,
                                json_decoder_class=None,
                                cipher=None,
                                record_class=None,
                                contiguous_record_ids=False):
    sequenced_item_class = sequenced_item_class or StoredEvent
    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=sequenced_item_class,
        sequence_id_attr_name=sequence_id_attr_name,
        position_attr_name=position_attr_name,
        json_encoder_class=json_encoder_class,
        json_decoder_class=json_decoder_class,
        cipher=cipher,
    )
    factory = DjangoInfrastructureFactory(
        integer_sequenced_record_class=record_class or StoredEventRecord,
        sequenced_item_class=sequenced_item_class,
        contiguous_record_ids=contiguous_record_ids,
    )
    record_manager = factory.construct_integer_sequenced_record_manager()
    event_store = EventStore(
        record_manager=record_manager,
        sequenced_item_mapper=sequenced_item_mapper,
    )
    return event_store
