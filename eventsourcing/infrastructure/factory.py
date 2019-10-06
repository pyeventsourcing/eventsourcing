from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.infrastructure.datastore import AbstractDatastore
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import (
    AbstractSequencedItemMapper,
    SequencedItemMapper,
)


class InfrastructureFactory(object):
    """
    Base class for infrastructure factories.
    """

    record_manager_class = None
    sequenced_item_class = SequencedItem
    sequenced_item_mapper_class = SequencedItemMapper
    integer_sequenced_record_class = None
    integer_sequenced_noid_record_class = None
    timestamp_sequenced_record_class = None
    snapshot_record_class = None
    json_encoder_class = None
    json_decoder_class = None
    event_store_class = EventStore

    def __init__(
        self,
        record_manager_class=None,
        sequenced_item_class=None,
        event_store_class=None,
        sequenced_item_mapper_class=None,
        json_encoder_class=None,
        json_decoder_class=None,
        integer_sequenced_record_class=None,
        timestamp_sequenced_record_class=None,
        snapshot_record_class=None,
        contiguous_record_ids=False,
        application_name=None,
        pipeline_id=DEFAULT_PIPELINE_ID,
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
        self.json_decoder_class = json_decoder_class or type(self).json_decoder_class

        self._integer_sequenced_record_class = integer_sequenced_record_class

        self._timestamp_sequenced_record_class = timestamp_sequenced_record_class

        self._snapshot_record_class = snapshot_record_class

        self.contiguous_record_ids = contiguous_record_ids
        self.application_name = application_name
        self.pipeline_id = pipeline_id

    def construct_integer_sequenced_record_manager(self, **kwargs):
        """
        Constructs an integer sequenced record manager.
        """
        integer_sequenced_record_class = (
            self._integer_sequenced_record_class or self.integer_sequenced_record_class
        )

        return self.construct_record_manager(integer_sequenced_record_class, **kwargs)

    def construct_timestamp_sequenced_record_manager(self, **kwargs):
        """
        Constructs a timestamp sequenced record manager.
        """
        timestamp_sequenced_record_class = (
            self._timestamp_sequenced_record_class
            or self.timestamp_sequenced_record_class
        )

        return self.construct_record_manager(timestamp_sequenced_record_class, **kwargs)

    def construct_snapshot_record_manager(self, **kwargs):
        """
        Constructs a snapshot record manager.
        """
        snapshot_record_class = (
            self._snapshot_record_class or self.snapshot_record_class
        )

        return self.construct_record_manager(snapshot_record_class, **kwargs)

    def construct_record_manager(
        self, record_class, sequenced_item_class=None, **kwargs
    ):
        """
        Constructs an record manager.
        """
        return self.record_manager_class(
            sequenced_item_class=sequenced_item_class or self.sequenced_item_class,
            record_class=record_class,
            contiguous_record_ids=self.contiguous_record_ids,
            application_name=self.application_name,
            pipeline_id=self.pipeline_id,
            **kwargs
        )

    def construct_sequenced_item_mapper(self, cipher):
        """
        Constructs sequenced item mapper object.

        :returns: Sequenced item mapper object.
        :rtype: AbstractSequencedItemMapper
        """
        return self.sequenced_item_mapper_class(
            sequenced_item_class=self.sequenced_item_class,
            cipher=cipher,
            # sequence_id_attr_name=sequence_id_attr_name,
            # position_attr_name=position_attr_name,
            json_encoder_class=self.json_encoder_class,
            json_decoder_class=self.json_decoder_class,
        )

    def construct_integer_sequenced_event_store(self, cipher):
        """
        Constructs an integer sequenced event store.
        """
        sequenced_item_mapper = self.construct_sequenced_item_mapper(cipher)
        record_manager = self.construct_integer_sequenced_record_manager()
        return self.event_store_class(
            record_manager, sequenced_item_mapper=sequenced_item_mapper
        )

    def construct_datastore(self):
        """
        Constructs datastore object.

        :returns: Concrete datastore object object.
        :rtype: AbstractDatastore
        """
        return None
