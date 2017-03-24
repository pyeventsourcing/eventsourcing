from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import SequencedItemError
from eventsourcing.infrastructure.transcoding import SequencedItem


class AbstractActiveRecordStrategy(six.with_metaclass(ABCMeta)):

    def __init__(self, active_record_class, sequenced_item_class=SequencedItem):
        self.active_record_class = active_record_class
        self.sequenced_item_class = sequenced_item_class

    @abstractmethod
    def append_item(self, sequenced_item):
        """
        Writes sequenced item into the datastore.
        """

    @abstractmethod
    def get_item(self, sequence_id, eq):
        """
        Reads sequenced item from the datastore.
        """

    @abstractmethod
    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):
        """
        Reads sequenced items from the datastore.
        """

    @abstractmethod
    def all_items(self):
        """
        Returns all items from all sequences (possibly in chronological order, depending on database).
        """

    def raise_sequence_item_error(self, sequence_id, position, e):
        raise SequencedItemError("Item at position '{}' already exists in sequence '{}': {}"
                                 "".format(position, sequence_id, e))

    def raise_index_error(self, eq):
        raise IndexError("Sequence index out of range: {}".format(eq))
