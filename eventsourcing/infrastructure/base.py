from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import SequencedItemConflict
from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames


class AbstractRecordManager(six.with_metaclass(ABCMeta)):
    def __init__(self, record_class, sequenced_item_class=SequencedItem):
        self.record_class = record_class
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

    def list_items(self, *args, **kwargs):
        return list(self.get_items(*args, **kwargs))

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
    def all_records(self, *arg, **kwargs):
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

    def raise_sequenced_item_error(self, sequenced_item):
        sequenced_item = sequenced_item[0] if isinstance(sequenced_item, list) else sequenced_item
        raise SequencedItemConflict("Item at position '{}' already exists in sequence '{}'"
                                 "".format(sequenced_item[1], sequenced_item[0]))

    def raise_index_error(self, eq):
        raise IndexError("Sequence index out of range: {}".format(eq))


class RelationalRecordManager(AbstractRecordManager):
    def append(self, sequenced_item_or_items):
        # Convert sequenced item(s) to active_record(s).
        if isinstance(sequenced_item_or_items, list):
            active_records = [self.to_active_record(i) for i in sequenced_item_or_items]
        else:
            active_records = [self.to_active_record(sequenced_item_or_items)]

        self._write_active_records(active_records, sequenced_item_or_items)

    def to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        # Check we got a sequenced item.
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Construct and return an ORM object.
        kwargs = self.get_field_kwargs(sequenced_item)
        return self.record_class(**kwargs)

    @abstractmethod
    def _write_active_records(self, active_records, sequenced_items):
        """
        Actually creates records in the database.
        """
