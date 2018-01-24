from eventsourcing.infrastructure.base import AbstractRecordManager
from eventsourcing.infrastructure.sequenceditem import SequencedItem


class InfrastructureFactory(object):
    record_manager_class = AbstractRecordManager
    sequenced_item_class = SequencedItem
    integer_sequenced_record_class = None
    integer_sequenced_noid_record_class = None
    timestamp_sequenced_record_class = None
    snapshot_record_class = None

    def __init__(self, record_manager_class=None, sequenced_item_class=None,
                 integer_sequenced_record_class=None, timestamp_sequenced_record_class=None,
                 snapshot_record_class=None, contiguous_record_ids=False, session=None):

        self.record_manager_class = record_manager_class or self.record_manager_class

        self.sequenced_item_class = sequenced_item_class or self.sequenced_item_class

        self.integer_sequenced_record_class = integer_sequenced_record_class or self.integer_sequenced_record_class

        self.timestamp_sequenced_record_class = timestamp_sequenced_record_class or \
                                                self.timestamp_sequenced_record_class

        self.snapshot_record_class = snapshot_record_class or self.snapshot_record_class

        self.contiguous_record_ids = contiguous_record_ids
        self.session = session

    def construct_integer_sequenced_record_manager(self, record_class=None):
        record_class = record_class or self.integer_sequenced_record_class
        assert self.integer_sequenced_record_class
        return self.construct_record_manager(
            record_class=record_class,
            sequenced_item_class=self.sequenced_item_class
        )

    def construct_timestamp_sequenced_record_manager(self, record_class=None):
        record_class = record_class or self.timestamp_sequenced_record_class
        assert self.integer_sequenced_record_class
        return self.construct_record_manager(
            record_class=record_class,
            sequenced_item_class=self.sequenced_item_class
        )

    def construct_snapshot_record_manager(self):
        return self.construct_record_manager(
            record_class=self.snapshot_record_class,
            sequenced_item_class=self.sequenced_item_class
        )

    def construct_record_manager(self, sequenced_item_class, record_class, **kwargs):
        return self.record_manager_class(
            sequenced_item_class=sequenced_item_class,
            record_class=record_class,
            contiguous_record_ids=self.contiguous_record_ids,
            **kwargs
        )
