from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import OperationalError, RecordConflictError
from eventsourcing.infrastructure.sequenceditem import SequencedItem, SequencedItemFieldNames


class AbstractSequencedItemRecordManager(six.with_metaclass(ABCMeta)):
    def __init__(self, record_class, sequenced_item_class=SequencedItem,
                 contiguous_record_ids=False, application_name=None, pipeline_id=-1):
        self.record_class = record_class
        self.sequenced_item_class = sequenced_item_class
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.contiguous_record_ids = contiguous_record_ids and hasattr(self.record_class, 'id')
        if hasattr(self.record_class, 'application_name'):
            assert application_name, "'application_name' not set when required"
            assert contiguous_record_ids, "'contiguous_record_ids' not set when required"
        self.application_name = application_name
        if hasattr(self.record_class, 'pipeline_id'):
            assert hasattr(self.record_class, 'application_name'), "'application_name' column not defined"
        self.pipeline_id = pipeline_id

    def clone(self, application_name, pipeline_id, **kwargs):
        return type(self)(
            record_class=self.record_class,
            contiguous_record_ids=self.contiguous_record_ids,
            sequenced_item_class=self.sequenced_item_class,
            application_name=application_name,
            pipeline_id=pipeline_id,
            **kwargs
        )

    @abstractmethod
    def append(self, sequenced_item_or_items):
        """
        Writes sequenced item into the datastore.
        """

    def get_item(self, sequence_id, position):
        """
        Gets sequenced item from the datastore.
        """
        return self.from_record(self.get_record(sequence_id, position))

    @abstractmethod
    def get_record(self, sequence_id, position):
        """
        Gets record at position in sequence.
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
        if hasattr(self.record_class, 'application_name'):
            kwargs['application_name'] = self.application_name
        try:
            return self.record_class(**kwargs)
        except TypeError as e:
            raise

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


class ACIDRecordManager(AbstractSequencedItemRecordManager):
    """
    ACID record managers can write tracking records and event records
    in an atomic transaction, needed for atomic processing in process
    applications.
    """
    tracking_record_class = None

    tracking_record_field_names = [
        'application_name',
        'upstream_application_name',
        'pipeline_id',
        'notification_id',
        # 'originator_id',
        # 'originator_version',
    ]

    @abstractmethod
    def write_records(self, records, tracking_kwargs=None):
        """
        Writes tracking, event and notification records for a process event.
        """

    @abstractmethod
    def get_max_record_id(self):
        """Return maximum notification ID in pipeline."""

    @abstractmethod
    def get_max_tracking_record_id(self, upstream_application_name):
        """Return maximum tracking record ID for notification from upstream application in pipeline."""

    @abstractmethod
    def has_tracking_record(self, upstream_application_name, pipeline_id, notification_id):
        """
        True if tracking record exists for notification from upstream in pipeline.
        """


class RelationalRecordManager(ACIDRecordManager):
    """
    This is has code common to (extracted from) the SQLAlchemy and Django record managers.

    This makes the subclasses harder to read and probably more brittle. So it might be better
    to inline this with the subclasses, so that each looks more like normal Django or SQLAlchemy
    code. Also, the record manager test cases don't cover the notification log and tracking record
    functionality needed by ProcessApplication, and should so that other record managers can more
    easily be developed.
    """
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

    @property
    def insert_select_max(self):
        """
        SQL statement that inserts records with contiguous IDs,
        by selecting max ID from indexed table records.
        """
        if self._insert_select_max is None:
            if hasattr(self.record_class, 'application_name'):
                # Todo: Maybe make it support application_name without pipeline_id?
                assert hasattr(self.record_class, 'pipeline_id'), self.record_class
                tmpl = self._insert_select_max_tmpl + self._where_application_name_tmpl
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
        "FROM {tablename}"
    )

    _where_application_name_tmpl = None

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
    def get_record_table_name(self, record_class):
        """
        Returns table name - used in raw queries.

        :rtype: str
        """

    def get_pipeline_and_notification_id(self, sequence_id, position):
        """
        Returns pipeline ID and notification ID for
        event at given position in given sequence.
        """
        # Todo: Optimise query by selecting only two columns: pipeline_id and id (notification ID).
        record = self.get_record(sequence_id, position)
        return record.pipeline_id, record.id


class AbstractTrackingRecordManager(six.with_metaclass(ABCMeta)):

    @property
    @abstractmethod
    def record_class(self):
        """Returns tracking record class."""

    @abstractmethod
    def get_max_record_id(self, application_name, upstream_application_name, pipeline_id):
        """Returns maximum record ID for given application name."""
