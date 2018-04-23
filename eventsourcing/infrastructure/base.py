from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import OperationalError, RecordConflictError
from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames


class AbstractSequencedItemRecordManager(six.with_metaclass(ABCMeta)):
    def __init__(self, record_class, sequenced_item_class=SequencedItem, contiguous_record_ids=False,
                 application_id=None, pipeline_id=-1):
        self.record_class = record_class
        self.sequenced_item_class = sequenced_item_class
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.contiguous_record_ids = contiguous_record_ids and hasattr(self.record_class, 'id')
        if hasattr(self.record_class, 'application_id'):
            assert application_id, "'application_id' not set when required"
            assert contiguous_record_ids, "'contiguous_record_ids' not set when required"
        self.application_id = application_id
        if hasattr(self.record_class, 'pipeline_id'):
            assert hasattr(self.record_class, 'application_id'), "'application_id' column not defined"
        self.pipeline_id = pipeline_id

    @abstractmethod
    def append(self, sequenced_item_or_items):
        """
        Writes sequenced item into the datastore.
        """

    @abstractmethod
    def get_item(self, sequence_id, position):
        """
        Gets sequenced item from the datastore.
        """

    def list_items(self, *args, **kwargs):
        return list(self.get_items(*args, **kwargs))

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):
        """
        Returns sequenced items.
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

    def to_record(self, sequenced_item):
        """
        Constructs and returns an ORM object, from given sequenced item object.
        """
        kwargs = self.get_field_kwargs(sequenced_item)
        if hasattr(self.record_class, 'application_id'):
            kwargs['application_id'] = self.application_id
        return self.record_class(**kwargs)

    def from_record(self, record):
        """
        Constructs and returns a sequenced item object, from given ORM object.
        """
        kwargs = self.get_field_kwargs(record)
        return self.sequenced_item_class(**kwargs)

    @abstractmethod
    def get_notifications(self, start=None, stop=None, *args, **kwargs):
        """
        Returns records sequenced by notification ID, from application, for pipeline, in given range.
        """

    @abstractmethod
    def all_sequence_ids(self):
        """
        Returns all sequence IDs.
        """

    def list_sequence_ids(self):
        return list(self.all_sequence_ids())

    @abstractmethod
    def delete_record(self, record):
        """
        Removes permanently given record from the table.
        """

    def get_field_kwargs(self, item):
        return {name: getattr(item, name) for name in self.field_names}

    def raise_sequenced_item_conflict(self):
        msg = "Position already taken in sequence"
        raise RecordConflictError(msg)

    def raise_index_error(self, position):
        raise IndexError("Sequence index out of range: {}".format(position))

    def raise_record_integrity_error(self, e):
        raise RecordConflictError(e)

    def raise_operational_error(self, e):
        raise OperationalError(e)


class RelationalRecordManager(AbstractSequencedItemRecordManager):
    tracking_record_class = None

    tracking_record_field_names = [
        'application_id',
        'upstream_application_id',
        'pipeline_id',
        'notification_id',
        # 'originator_id',
        # 'originator_version',
    ]

    def __init__(self, *args, **kwargs):
        super(RelationalRecordManager, self).__init__(*args, **kwargs)
        self._insert_select_max = None
        self._insert_values = None
        self._insert_tracking_record = None

    def append(self, sequenced_item_or_items):
        # Convert sequenced item(s) to database record(s).
        records = self.to_records(sequenced_item_or_items)

        # Write records.
        self.write_records(records)

    def to_records(self, sequenced_item_or_items):
        if isinstance(sequenced_item_or_items, list):
            records = [self.to_record(i) for i in sequenced_item_or_items]
        else:
            records = [self.to_record(sequenced_item_or_items)]
        return records

    def write_records(self, records, tracking_kwargs=None):
        """
        Calls _write_records() implemented by concrete classes.

        :param tracking_kwargs:
        """
        self._write_records(records, tracking_kwargs=tracking_kwargs)

    # Todo: Remove this now that we have no retry decorator on above.
    @abstractmethod
    def _write_records(self, records, tracking_kwargs=None):
        """
        Actually creates records in the database.
        :param tracking_kwargs:
        """

    @property
    def insert_select_max(self):
        """
        SQL statement that inserts records with contiguous IDs,
        by selecting max ID from indexed table records.
        """
        if self._insert_select_max is None:
            if hasattr(self.record_class, 'application_id'):
                # Todo: Maybe make it support application_id with pipeline_id?
                assert hasattr(self.record_class, 'pipeline_id')
                tmpl = self._insert_select_max_where_application_id_tmpl
            else:
                tmpl = self._insert_select_max_tmpl
            self._insert_select_max = self._prepare_insert(
                tmpl=tmpl,
                record_class=self.record_class,
                field_names=list(self.field_names),
            )
        return self._insert_select_max

    @abstractmethod
    def _prepare_insert(self, tmpl, record_class, field_names, placeholder_for_id=False):
        """
        Compile SQL statement with placeholders for bind parameters.
        """

    _insert_select_max_tmpl = (
        "INSERT INTO {tablename} (id, {columns}) "
        "SELECT COALESCE(MAX({tablename}.id), 0) + 1, {placeholders} "
        "FROM {tablename};"
    )

    _insert_select_max_where_application_id_tmpl = (
        "INSERT INTO {tablename} (id, {columns}) "
        "SELECT COALESCE(MAX({tablename}.id), 0) + 1, {placeholders} "
        "FROM {tablename} WHERE application_id=:application_id AND pipeline_id=:pipeline_id;"
    )

    @property
    def insert_values(self):
        """
        SQL statement that inserts records without ID.
        """
        if self._insert_values is None:
            self._insert_values = self._prepare_insert(
                tmpl=self._insert_values_tmpl,
                placeholder_for_id=True,
                record_class=self.record_class,
                field_names=self.field_names,
            )
        return self._insert_values

    @property
    def insert_tracking_record(self):
        """
        SQL statement that inserts tracking records.
        """
        if self._insert_tracking_record is None:
            self._insert_tracking_record = self._prepare_insert(
                tmpl=self._insert_values_tmpl,
                placeholder_for_id=True,
                record_class=self.tracking_record_class,
                field_names=self.tracking_record_field_names,
            )
        return self._insert_tracking_record

    _insert_values_tmpl = (
        "INSERT INTO {tablename} ({columns}) "
        "VALUES ({placeholders});"
    )

    @abstractmethod
    def get_max_record_id(self):
        """Return maximum ID of existing records."""

    @abstractmethod
    def get_record_table_name(self, record_class):
        """
        Returns table name - used in raw queries.

        :rtype: str
        """


class AbstractTrackingRecordManager(six.with_metaclass(ABCMeta)):

    @property
    @abstractmethod
    def record_class(self):
        """Returns tracking record class."""

    @abstractmethod
    def get_max_record_id(self, application_name, upstream_application_name, pipeline_id):
        """Returns maximum record ID for given application name."""
