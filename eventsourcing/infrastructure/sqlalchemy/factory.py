from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, StoredEventRecord


def construct_sqlalchemy_eventstore(session, active_record_class=StoredEventRecord, sequenced_item_class=StoredEvent,
                                    sequence_id_attr_name=None, position_attr_name=None):
    # Todo: Expose other args of SequencedItemMapper as args of this function.
    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=sequenced_item_class,
        sequence_id_attr_name=sequence_id_attr_name,
        position_attr_name=position_attr_name,
    )
    # Todo: Expose other args of SQLAlchemyActiveRecordStrategy as args of this function.
    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        session=session,
        active_record_class=active_record_class,
        sequenced_item_class = sequenced_item_class,
    )
    # Todo: Expose other args of EventStore as args of this function.
    return EventStore(
        active_record_strategy=active_record_strategy,
        sequenced_item_mapper=sequenced_item_mapper,
    )
