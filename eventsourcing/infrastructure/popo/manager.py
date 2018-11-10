from eventsourcing.exceptions import RecordConflictError
from eventsourcing.infrastructure.base import ACIDRecordManager


class PopoRecordManager(ACIDRecordManager):

    def __init__(self, *args, **kwargs):
        super(PopoRecordManager, self).__init__(*args, **kwargs)
        self._all_sequence_records = {}

    def all_sequence_ids(self):
        return self._all_sequence_records.keys()

    def delete_record(self, record):
        all_sequence_ids = self._get_all_sequence_records(record.sequence_id)
        try:
            del(all_sequence_ids[record.position])
        except KeyError:
            pass

    def get_max_record_id(self):
        raise NotImplementedError()

    def get_max_tracking_record_id(self, upstream_application_name):
        raise NotImplementedError()

    def get_notifications(self, start=None, stop=None, *args, **kwargs):
        raise NotImplementedError()

    def get_record(self, sequence_id, position):
        try:
            return self._get_all_sequence_records(sequence_id)[position]
        except KeyError:
            raise IndexError(self.application_name, sequence_id, position)

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):

        start = None
        if gt is not None:
            start = gt + 1
        if gte is not None:
            if start is None:
                start = gte
            else:
                start = max(start, gte)

        end = None
        if lt is not None:
            end = lt
        if lte is not None:
            if end is None:
                end = lte + 1
            else:
                end = min(end, lte + 1)

        all_sequence_records = self._get_all_sequence_records(sequence_id)
        if not len(all_sequence_records):
            return []

        if end is None:
            end = max(all_sequence_records.keys()) + 1
        if start is None:
            start = min(all_sequence_records.keys())

        selected_records = []
        for position in range(start, end):
            try:
                record = all_sequence_records[position]
            except KeyError:
                pass
            else:
                selected_records.append(record)

        if not query_ascending:
            selected_records = reversed(selected_records)

        if limit is not None:
            selected_records = list(selected_records)[:limit]

        if query_ascending != results_ascending:
            selected_records = reversed(selected_records)

        return selected_records

    def _get_all_sequence_records(self, sequence_id):
        try:
            return self._all_sequence_records[sequence_id]
        except KeyError:
            return {}

    def has_tracking_record(self, upstream_application_name, pipeline_id, notification_id):
        raise NotImplementedError()

    def record(self, sequenced_item_or_items):
        if isinstance(sequenced_item_or_items, list):
            for sequenced_item in sequenced_item_or_items:
                self._record_sequenced_item(sequenced_item)
        else:
            self._record_sequenced_item(sequenced_item_or_items)

    def _record_sequenced_item(self, sequenced_item):
        if not isinstance(sequenced_item.position, int):
            raise NotImplementedError("Popo record manager only supports sequencing with integers, "
                                      "but position was a {}".format(type(sequenced_item.position)))
        try:
            all_records = self._all_sequence_records[sequenced_item.sequence_id]
        except KeyError:
            all_records = {}
            self._all_sequence_records[sequenced_item.sequence_id] = all_records
        if sequenced_item.position in all_records:
            raise RecordConflictError(sequenced_item.position, len(all_records))
        all_records[sequenced_item.position] = sequenced_item

    def write_records(self, records, tracking_kwargs=None):
        raise NotImplementedError()
