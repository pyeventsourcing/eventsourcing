from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import SequencedItemError
from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames


class AbstractActiveRecordStrategy(six.with_metaclass(ABCMeta)):
    def __init__(self, active_record_class, sequenced_item_class=SequencedItem):
        self.active_record_class = active_record_class
        self.sequenced_item_class = sequenced_item_class
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)

    @abstractmethod
    def append(self, sequenced_item_or_items):
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
        Returns all stored items from all sequences (possibly in chronological order, depending on database).
        """

    @abstractmethod
    def all_records(self, resume=None, *arg, **kwargs):
        """
        Returns all records in the table (possibly in chronological order, depending on database).
        """

    @abstractmethod
    def delete_record(self, record):
        """
        Removes permanently given record from the table.
        """

    def get_field_kwargs(self, item):
        return {name: getattr(item, name) for name in self.field_names}

    def raise_sequenced_item_error(self, sequenced_item, e):
        sequenced_item = sequenced_item[0] if isinstance(sequenced_item, list) else sequenced_item
        raise SequencedItemError("Item at position '{}' already exists in sequence '{}': {}"
                                 "".format(sequenced_item[1], sequenced_item[0], e))

    def raise_index_error(self, eq):
        raise IndexError("Sequence index out of range: {}".format(eq))
