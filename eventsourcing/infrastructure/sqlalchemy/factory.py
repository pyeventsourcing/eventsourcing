from typing import Any, NamedTuple, Optional, Type

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID, AbstractRecordManager
from eventsourcing.infrastructure.datastore import AbstractDatastore
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.datastore import (
    SQLAlchemyDatastore,
    SQLAlchemySettings,
)
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import (
    IntegerSequencedWithIDRecord,
    NotificationTrackingRecord,
    SnapshotRecord,
    StoredEventRecord,
    TimestampSequencedNoIDRecord,
)
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder


class SQLAlchemyInfrastructureFactory(InfrastructureFactory):
    """
    Infrastructure factory for SQLAlchemy infrastructure.
    """

    record_manager_class = SQLAlchemyRecordManager
    integer_sequenced_record_class = IntegerSequencedWithIDRecord
    timestamp_sequenced_record_class = TimestampSequencedNoIDRecord
    snapshot_record_class = SnapshotRecord
    tracking_record_class = NotificationTrackingRecord

    def __init__(
        self,
        session: Any,
        uri: Optional[str] = None,
        pool_size: Optional[int] = None,
        tracking_record_class: Optional[type] = None,
        *args: Any,
        **kwargs: Any
    ):
        super(SQLAlchemyInfrastructureFactory, self).__init__(*args, **kwargs)
        self.session = session
        self.uri = uri
        self.pool_size = pool_size
        self._tracking_record_class = tracking_record_class

    def construct_integer_sequenced_record_manager(
        self, **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs SQLAlchemy record manager.

        :return: An SQLAlchemy record manager.
        :rtype: SQLAlchemyRecordManager
        """
        tracking_record_class = (
            self._tracking_record_class or self.tracking_record_class
        )
        return super(
            SQLAlchemyInfrastructureFactory, self
        ).construct_integer_sequenced_record_manager(
            tracking_record_class=tracking_record_class, **kwargs
        )

    def construct_record_manager(
        self,
        record_class: Optional[type],
        sequenced_item_class: Optional[Type[NamedTuple]] = None,
        **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs SQLAlchemy record manager.

        :return: An SQLAlchemy record manager.
        :rtype: SQLAlchemyRecordManager
        """
        return super(SQLAlchemyInfrastructureFactory, self).construct_record_manager(
            record_class,
            sequenced_item_class=sequenced_item_class,
            session=self.session,
            **kwargs
        )

    def construct_datastore(self) -> Optional[AbstractDatastore]:
        """
        Constructs SQLAlchemy datastore.

        :rtype: SQLAlchemyDatastore
        """
        datastore = SQLAlchemyDatastore(
            settings=SQLAlchemySettings(uri=self.uri, pool_size=self.pool_size),
            session=self.session,
        )
        if self.session is None:
            assert datastore.session, "Datastore object session is None"
            self.session = datastore.session
        return datastore


def construct_sqlalchemy_eventstore(
    session: Any,
    sequenced_item_class: Optional[Type[NamedTuple]] = None,
    sequence_id_attr_name: Optional[str] = None,
    position_attr_name: Optional[str] = None,
    json_encoder_class: Optional[Type[ObjectJSONEncoder]] = None,
    json_decoder_class: Optional[Type[ObjectJSONDecoder]] = None,
    cipher: Optional[AESCipher] = None,
    record_class: Optional[type] = None,
    contiguous_record_ids: bool = False,
    application_name: Optional[str] = None,
    pipeline_id: int = DEFAULT_PIPELINE_ID,
) -> EventStore:
    sequenced_item_class = sequenced_item_class or StoredEvent  # type: ignore
    sequenced_item_mapper = SequencedItemMapper[DomainEvent](
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
    event_store = EventStore[DomainEvent, AbstractRecordManager](
        record_manager=record_manager, event_mapper=sequenced_item_mapper
    )
    return event_store
