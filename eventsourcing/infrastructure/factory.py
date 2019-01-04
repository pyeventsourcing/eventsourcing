from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.infrastructure.sequenceditem import SequencedItem


class InfrastructureFactory(object):
    record_manager_class = None
    sequenced_item_class = SequencedItem
    integer_sequenced_record_class = None
    integer_sequenced_noid_record_class = None
    timestamp_sequenced_record_class = None
    snapshot_record_class = None

    def __init__(self, record_manager_class=None, sequenced_item_class=None,
                 integer_sequenced_record_class=None, timestamp_sequenced_record_class=None,
                 snapshot_record_class=None, contiguous_record_ids=False, application_name=None,
                 pipeline_id=DEFAULT_PIPELINE_ID):

        self.record_manager_class = record_manager_class or self.record_manager_class

        self.sequenced_item_class = sequenced_item_class or self.sequenced_item_class

        self.integer_sequenced_record_class = integer_sequenced_record_class or self.integer_sequenced_record_class

        self.timestamp_sequenced_record_class = timestamp_sequenced_record_class or \
                                                self.timestamp_sequenced_record_class

        self.snapshot_record_class = snapshot_record_class or self.snapshot_record_class

        self.contiguous_record_ids = contiguous_record_ids
        self.application_name = application_name
        self.pipeline_id = pipeline_id

    def construct_integer_sequenced_record_manager(self, record_class=None):
        return self.construct_record_manager(
            record_class=record_class or self.integer_sequenced_record_class,
        )

    def construct_timestamp_sequenced_record_manager(self, record_class=None):
        record_class = record_class or self.timestamp_sequenced_record_class
        # assert self.integer_sequenced_record_class
        return self.construct_record_manager(
            record_class=record_class,
        )

    def construct_snapshot_record_manager(self):
        return self.construct_record_manager(
            record_class=self.snapshot_record_class,
        )

    def construct_record_manager(self, record_class, sequenced_item_class=None, **kwargs):
        return self.record_manager_class(
            sequenced_item_class=sequenced_item_class or self.sequenced_item_class,
            record_class=record_class,
            contiguous_record_ids=self.contiguous_record_ids,
            application_name=self.application_name,
            pipeline_id=self.pipeline_id,
            **kwargs
        )

    def construct_datastore(self):
        return None
