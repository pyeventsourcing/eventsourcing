from json import JSONDecoder, JSONEncoder
from typing import Any, Generic, NamedTuple, Optional, Type

from eventsourcing.infrastructure.base import (
    DEFAULT_PIPELINE_ID,
    AbstractEventStore,
    AbstractRecordManager,
)
from eventsourcing.infrastructure.datastore import AbstractDatastore
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import (
    AbstractSequencedItemMapper,
    SequencedItemMapper,
)
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.whitehead import TEvent


class InfrastructureFactory(Generic[TEvent]):
    """
    Base class for infrastructure factories.
    """

    record_manager_class: Optional[Type[AbstractRecordManager]] = None
    sequenced_item_class: Type[NamedTuple] = SequencedItem  # type: ignore
    sequenced_item_mapper_class: Type[AbstractSequencedItemMapper] = SequencedItemMapper
    integer_sequenced_record_class: Optional[type] = None
    integer_sequenced_noid_record_class: Optional[type] = None
    timestamp_sequenced_record_class: Optional[type] = None
    snapshot_record_class: Optional[type] = None
    json_decoder_class: Optional[Type[JSONDecoder]] = None
    json_encoder_class: Optional[Type[JSONEncoder]] = None
    event_store_class: Optional[Type[AbstractEventStore]] = None

    def __init__(
        self,
        record_manager_class: Optional[Type[AbstractRecordManager]] = None,
        sequenced_item_class: Optional[Type[NamedTuple]] = None,
        event_store_class: Optional[Type[AbstractEventStore]] = None,
        sequenced_item_mapper_class: Optional[Type[AbstractSequencedItemMapper]] = None,
        json_encoder_class: Optional[Type[JSONEncoder]] = None,
        sort_keys: bool = False,
        json_decoder_class: Optional[Type[JSONDecoder]] = None,
        integer_sequenced_record_class: Optional[type] = None,
        timestamp_sequenced_record_class: Optional[type] = None,
        snapshot_record_class: Optional[type] = None,
        contiguous_record_ids: bool = False,
        application_name: Optional[str] = None,
        pipeline_id: int = DEFAULT_PIPELINE_ID,
    ):
        self.record_manager_class = (
            record_manager_class or type(self).record_manager_class
        )
        self.event_store_class = event_store_class or type(self).event_store_class
        self.sequenced_item_class = (
            sequenced_item_class or type(self).sequenced_item_class
        )
        self.sequenced_item_mapper_class = (
            sequenced_item_mapper_class or type(self).sequenced_item_mapper_class
        )
        self.json_encoder_class = json_encoder_class or type(self).json_encoder_class
        self.sort_keys = sort_keys
        self.json_decoder_class = json_decoder_class or type(self).json_decoder_class

        self._integer_sequenced_record_class = integer_sequenced_record_class

        self._timestamp_sequenced_record_class = timestamp_sequenced_record_class

        self._snapshot_record_class = snapshot_record_class

        self.contiguous_record_ids = contiguous_record_ids
        self.application_name = application_name
        self.pipeline_id = pipeline_id

    def construct_integer_sequenced_record_manager(
        self, **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs an integer sequenced record manager.
        """
        integer_sequenced_record_class = (
            self._integer_sequenced_record_class or self.integer_sequenced_record_class
        )
        return self.construct_record_manager(integer_sequenced_record_class, **kwargs)

    def construct_timestamp_sequenced_record_manager(
        self, **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs a timestamp sequenced record manager.
        """
        timestamp_sequenced_record_class = (
            self._timestamp_sequenced_record_class
            or self.timestamp_sequenced_record_class
        )
        return self.construct_record_manager(timestamp_sequenced_record_class, **kwargs)

    def construct_snapshot_record_manager(self, **kwargs: Any) -> AbstractRecordManager:
        """
        Constructs a snapshot record manager.
        """
        snapshot_record_class = (
            self._snapshot_record_class or self.snapshot_record_class
        )
        return self.construct_record_manager(snapshot_record_class, **kwargs)

    def construct_record_manager(
        self,
        record_class: Optional[type],
        sequenced_item_class: Optional[Type[NamedTuple]] = None,
        **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs an record manager.
        """
        assert self.record_manager_class is not None
        return self.record_manager_class(
            sequenced_item_class=sequenced_item_class or self.sequenced_item_class,
            record_class=record_class,
            contiguous_record_ids=self.contiguous_record_ids,
            application_name=self.application_name,
            pipeline_id=self.pipeline_id,
            **kwargs
        )

    def construct_sequenced_item_mapper(
        self, cipher: Optional[AESCipher], compressor: Any,
    ) -> AbstractSequencedItemMapper:
        """
        Constructs sequenced item mapper object.

        :returns: Sequenced item mapper object.
        :rtype: eventsourcing.infrastructure.sequenceditemmapper
        .AbstractSequencedItemMapper
        """
        return self.sequenced_item_mapper_class(
            sequenced_item_class=self.sequenced_item_class,
            cipher=cipher,
            compressor=compressor,
            # sequence_id_attr_name=sequence_id_attr_name,
            # position_attr_name=position_attr_name,
            json_encoder_class=self.json_encoder_class,
            sort_keys=self.sort_keys,
            json_decoder_class=self.json_decoder_class,
        )

    def construct_integer_sequenced_event_store(
        self, cipher: Optional[AESCipher], compressor: Any,
    ) -> AbstractEventStore:
        """
        Constructs an integer sequenced event store.
        """
        sequenced_item_mapper = self.construct_sequenced_item_mapper(cipher, compressor)
        record_manager = self.construct_integer_sequenced_record_manager()
        return (self.event_store_class or EventStore)(
            record_manager=record_manager, event_mapper=sequenced_item_mapper
        )

    def construct_datastore(self) -> Optional[AbstractDatastore]:
        """
        Constructs datastore object.

        :returns: Concrete datastore object object.
        """
        return None
