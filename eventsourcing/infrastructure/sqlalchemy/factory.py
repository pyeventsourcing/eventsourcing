from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import IntegerSequencedWithIDRecord, SnapshotRecord, \
    StoredEventRecord, TimestampSequencedNoIDRecord


class SQLAlchemyInfrastructureFactory(InfrastructureFactory):
    record_manager_class = SQLAlchemyRecordManager
    integer_sequenced_record_class = IntegerSequencedWithIDRecord
    timestamp_sequenced_record_class = TimestampSequencedNoIDRecord
    snapshot_record_class = SnapshotRecord

    def __init__(self, session, uri=None, pool_size=None, *args, **kwargs):
        super(SQLAlchemyInfrastructureFactory, self).__init__(*args, **kwargs)
        self.session = session
        self.uri = uri
        self.pool_size = pool_size

    def construct_record_manager(self, **kwargs):
        s = super(SQLAlchemyInfrastructureFactory, self)
        return s.construct_record_manager(session=self.session, **kwargs)

    def construct_datastore(self):
        datastore = SQLAlchemyDatastore(
            settings=SQLAlchemySettings(
                uri=self.uri,
                pool_size=self.pool_size
            ),
            session=self.session,
        )
        self.session = datastore.session
        return datastore


def construct_sqlalchemy_eventstore(session,
                                    sequenced_item_class=None,
                                    sequence_id_attr_name=None,
                                    position_attr_name=None,
                                    json_encoder_class=None,
                                    json_decoder_class=None,
                                    cipher=None,
                                    record_class=None,
                                    contiguous_record_ids=False,
                                    application_name=None,
                                    pipeline_id=DEFAULT_PIPELINE_ID,
                                    ):
    sequenced_item_class = sequenced_item_class or StoredEvent
    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=sequenced_item_class,
        sequence_id_attr_name=sequence_id_attr_name,
        position_attr_name=position_attr_name,
        json_encoder_class=json_encoder_class,
        json_decoder_class=json_decoder_class,
        cipher=cipher,
    )
    factory = SQLAlchemyInfrastructureFactory(
        session=session,
        integer_sequenced_record_class=record_class or StoredEventRecord,
        sequenced_item_class=sequenced_item_class,
        contiguous_record_ids=contiguous_record_ids,
        application_name=application_name,
        pipeline_id=pipeline_id,
    )
    record_manager = factory.construct_integer_sequenced_record_manager()
    event_store = EventStore(
        record_manager=record_manager,
        sequenced_item_mapper=sequenced_item_mapper,
    )
    return event_store
