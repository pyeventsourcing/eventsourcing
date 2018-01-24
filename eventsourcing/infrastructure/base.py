from abc import ABCMeta, abstractmethod

import six

from eventsourcing.domain.model.decorators import retry
from eventsourcing.exceptions import RecordIDConflict, SequencedItemConflict
from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames


class AbstractRecordManager(six.with_metaclass(ABCMeta)):
    def __init__(self, record_class, sequenced_item_class=SequencedItem, contiguous_record_ids=False):
        self.record_class = record_class
        self.sequenced_item_class = sequenced_item_class
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.contiguous_record_ids = contiguous_record_ids and hasattr(self.record_class, 'id')

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
    def all_records(self, start=None, stop=None, *args, **kwargs):
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

    def raise_sequenced_item_conflict(self):
        msg = "Position already taken in sequence"
        raise SequencedItemConflict(msg)

    def raise_index_error(self, eq):
        raise IndexError("Sequence index out of range: {}".format(eq))


class RelationalRecordManager(AbstractRecordManager):

    def __init__(self, *args, **kwargs):
        super(RelationalRecordManager, self).__init__(*args, **kwargs)
        self._insert_select_max = None
        self._insert_values = None

    def append(self, sequenced_item_or_items):
        # Convert sequenced item(s) to database record(s).
        if isinstance(sequenced_item_or_items, list):
            records = [self.to_record(i) for i in sequenced_item_or_items]
        else:
            records = [self.to_record(sequenced_item_or_items)]
        self.write_records(records)

    @retry(RecordIDConflict, max_attempts=100, wait=0.005)
    def write_records(self, records):
        """
        Calls _write_records() implemented by concrete classes.

        Retries call in case of a RecordIDConflict.
        """
        self._write_records(records)

    @abstractmethod
    def _write_records(self, records):
        """
        Actually creates records in the database.
        """

    @property
    def insert_select_max(self):
        """
        SQL statement that inserts records with contiguous IDs,
        by selecting max ID from indexed table records.
        """
        if self._insert_select_max is None:
            self._insert_select_max = self._prepare_insert(self._insert_select_max_tmpl)
        return self._insert_select_max

    @abstractmethod
    def _prepare_insert(self, tmpl):
        """
        Compile SQL statement with placeholders for bind parameters.
        """

    _insert_select_max_tmpl = (
        "INSERT INTO {tablename} (id, {columns}) "
        "SELECT COALESCE(MAX({tablename}.id), 0) + 1, {placeholders} "
        "FROM {tablename};"
    )

    @property
    def insert_values(self):
        """
        SQL statement that inserts records without ID.
        """
        if self._insert_values is None:
            self._insert_values = self._prepare_insert(tmpl=self._insert_values_tmpl)
        return self._insert_values

    _insert_values_tmpl = (
        "INSERT INTO {tablename} ({columns}) "
        "VALUES ({placeholders});"
    )

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):
        """
        Returns items of a sequence.
        """
        records = self.get_records(
            sequence_id=sequence_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            query_ascending=query_ascending,
            results_ascending=results_ascending,

        )
        for item in six.moves.map(self.from_record, records):
            yield item

    @abstractmethod
    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):
        """
        Returns records for a sequence.
        """

    def from_record(self, record):
        """
        Returns a sequenced item, from given database record.
        """
        kwargs = self.get_field_kwargs(record)
        return self.sequenced_item_class(**kwargs)

    def to_record(self, sequenced_item):
        """
        Returns a database record, from given sequenced item.
        """
        # Check we got a sequenced item.
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Construct and return an ORM object.
        kwargs = self.get_field_kwargs(sequenced_item)
        return self.record_class(**kwargs)

    # # Todo: Drop this, it doesn't really help.
    # def __getitem__(self, item=None):
    #     assert isinstance(item, slice), type(item)
    #     # start = item.start or 0
    #     # assert start >= 0, start
    #     return self.all_records(start=item.start, stop=item.stop)

    @abstractmethod
    def get_max_record_id(self):
        """Return maximum ID of existing records."""

    @property
    @abstractmethod
    def record_table_name(self):
        """
        Returns table name - used in raw queries,
        and to detect record ID conflicts.

        :rtype: str
        """

    def raise_after_integrity_error(self, e):
        error = str(e)

        # Try to identify record ID conflicts.
        if self.contiguous_record_ids:
            # Assume record ID is primary key.
            #  - SQLite
            if "UNIQUE constraint failed: {}.id".format(self.record_table_name) in error:
                self.raise_record_id_conflict()
            #  - MySQL
            elif 'Duplicate entry' in error and "for key 'PRIMARY'" in error:
                self.raise_record_id_conflict()
            #  - PostgreSQL
            elif 'duplicate key value violates unique constraint "{}_pkey"'.format(self.record_table_name) in error:
                self.raise_record_id_conflict()
        self.raise_sequenced_item_conflict()

    @staticmethod
    def raise_record_id_conflict():
        """
        Raises RecordIDConflict exception.
        """
        msg = "There was a record ID conflict"
        raise RecordIDConflict(msg)
