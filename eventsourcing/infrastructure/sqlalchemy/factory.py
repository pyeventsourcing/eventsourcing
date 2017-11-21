from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, StoredEventRecord
from eventsourcing.infrastructure.transcoding import ObjectJSONEncoder, ObjectJSONDecoder


def construct_sqlalchemy_eventstore(session,
                                    sequenced_item_class=StoredEvent,
                                    sequence_id_attr_name=None,
                                    position_attr_name=None,
                                    json_encoder_class=ObjectJSONEncoder,
                                    json_decoder_class=ObjectJSONDecoder,
                                    always_encrypt=False,
                                    cipher=None,
                                    active_record_class=StoredEventRecord,
                                    ):
    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=sequenced_item_class,
        sequence_id_attr_name=sequence_id_attr_name,
        position_attr_name=position_attr_name,
        json_encoder_class=json_encoder_class,
        json_decoder_class=json_decoder_class,
        always_encrypt=always_encrypt,
        cipher=cipher,
    )
    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        session=session,
        active_record_class=active_record_class,
        sequenced_item_class = sequenced_item_class,
    )
    event_store = EventStore(
        active_record_strategy=active_record_strategy,
        sequenced_item_mapper=sequenced_item_mapper,
    )
    return event_store
