from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.utils.transcoding import ObjectJSONEncoder, ObjectJSONDecoder


def construct_sqlalchemy_eventstore(session,
                                    sequenced_item_class=StoredEvent,
                                    sequence_id_attr_name=None,
                                    position_attr_name=None,
                                    json_encoder_class=ObjectJSONEncoder,
                                    json_decoder_class=ObjectJSONDecoder,
                                    cipher=None,
                                    record_class=None,
                                    contiguous_record_ids=False,
                                    ):
    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=sequenced_item_class,
        sequence_id_attr_name=sequence_id_attr_name,
        position_attr_name=position_attr_name,
        json_encoder_class=json_encoder_class,
        json_decoder_class=json_decoder_class,
        cipher=cipher,
    )
    record_manager = SQLAlchemyRecordManager(
        session=session,
        record_class=record_class or StoredEventRecord,
        sequenced_item_class=sequenced_item_class,
        contiguous_record_ids=contiguous_record_ids,
    )
    event_store = EventStore(
        record_manager=record_manager,
        sequenced_item_mapper=sequenced_item_mapper,
    )
    return event_store
