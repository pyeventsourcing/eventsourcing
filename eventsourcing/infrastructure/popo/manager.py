from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence
from uuid import UUID

from readerwriterlock.rwlock import RWLockFair

from eventsourcing.exceptions import RecordConflictError
from eventsourcing.infrastructure.base import RecordManagerWithTracking, TrackingKwargs


class PopoNotification(object):
    def __init__(
        self,
        notification_id: int,
        originator_id: UUID,
        originator_version: int,
        topic: str,
        state: str,
    ):
        self.notification_id = notification_id
        self.originator_id = originator_id
        self.originator_version = originator_version
        self.topic = topic
        self.state = state


class PopoRecordManager(RecordManagerWithTracking):
    def __init__(self, *args: Any, **kwargs: Any):
        super(PopoRecordManager, self).__init__(*args, **kwargs)
        self._all_sequence_records: Dict[
            Optional[str], Dict[UUID, Dict[int, NamedTuple]]
        ] = {}
        self._all_sequence_max: Dict = {}
        self._all_tracking_records: Dict = {}
        self._all_tracking_max: Dict = {}
        self._all_notification_records: Dict[Optional[str], Dict[int, Any]] = {}
        self._all_notification_max: Dict = {}
        self._rw_lock: RWLockFair = RWLockFair()

    def all_sequence_ids(self) -> List[UUID]:
        ids: List[UUID] = []
        with self._rw_lock.gen_rlock():
            try:
                ids = list(self._all_sequence_records[self.application_name].keys())
            except KeyError:
                pass
        return ids

    def delete_record(self, record: Any) -> None:
        with self._rw_lock.gen_wlock():
            sequence_records = self._get_sequence_records(record.sequence_id)
            position = getattr(record, self.field_names.position)
            sequence_records.pop(position, None)

    def get_max_notification_id(self) -> int:
        with self._rw_lock.gen_rlock():
            max_record_id = self._get_max_record_id()
        return max_record_id

    def _get_max_record_id(self) -> int:
        try:
            max_notification_id = self._all_notification_max[self.application_name]
        except KeyError:
            return 0
        else:
            return max_notification_id

    def _get_notification_records(self) -> Dict[int, Any]:
        notification_records: Dict[int, Any] = {}
        try:
            notification_records = self._all_notification_records[self.application_name]
        except KeyError:
            pass
        return notification_records

    def get_notification_records(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Iterable:
        notifications = []
        with self._rw_lock.gen_rlock():
            notification_records = self._get_notification_records()
            if start is None:
                i = 1
            else:
                i = start + 1
            while True:
                if stop is not None and i >= stop + 1:
                    break
                try:
                    notification_record = notification_records[i]
                    notification = PopoNotification(
                        notification_id=notification_record["notification_id"],
                        originator_id=notification_record[
                            "sequenced_item"
                        ].originator_id,
                        originator_version=notification_record[
                            "sequenced_item"
                        ].originator_version,
                        topic=notification_record["sequenced_item"].topic,
                        state=notification_record["sequenced_item"].state,
                    )
                    notifications.append(notification)
                except KeyError:
                    break
                else:
                    i += 1

        return notifications

    def get_max_tracking_record_id(self, upstream_application_name: str) -> int:
        max_id = 0
        with self._rw_lock.gen_rlock():
            try:
                app_records = self._all_tracking_records[self.application_name]
                upstream_records = app_records[upstream_application_name]
            except KeyError:
                pass
            else:
                if len(upstream_records):
                    max_id = max(upstream_records)
        return max_id

    def get_record(self, sequence_id: UUID, position: int) -> Any:
        with self._rw_lock.gen_rlock():
            try:
                return self._get_sequence_records(sequence_id)[position]
            except KeyError:
                raise IndexError(self.application_name, sequence_id, position)

    def get_records(
        self,
        sequence_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        query_ascending: bool = True,
        results_ascending: bool = True,
    ) -> Sequence[Any]:

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

        selected_records: List = []
        with self._rw_lock.gen_rlock():
            all_sequence_records = self._get_sequence_records(sequence_id)
            if not len(all_sequence_records):
                return []

            if end is None:
                max_position = self._all_sequence_max[self.application_name][
                    sequence_id
                ]
                end = max_position + 1
            if start is None:
                start = min(all_sequence_records.keys())

            for position in range(start, end):
                try:
                    record = all_sequence_records[position]
                except KeyError:
                    pass
                else:
                    selected_records.append(record)

            if not query_ascending:
                selected_records = list(reversed(selected_records))

            if limit is not None:
                selected_records = list(selected_records)[:limit]

            if query_ascending != results_ascending:
                selected_records = list(reversed(selected_records))

        return selected_records

    def _get_sequence_records(self, sequence_id: UUID) -> Dict:
        try:
            return self._all_sequence_records[self.application_name][sequence_id]
        except KeyError:
            return {}

    def has_tracking_record(
        self, upstream_application_name: str, pipeline_id: int, notification_id: int
    ) -> bool:
        raise NotImplementedError()

    def record_items(self, sequenced_items: Iterable[NamedTuple]) -> None:
        records = self.to_records(sequenced_items)
        self.write_records(records=records)

    def write_records(
        self,
        records: Iterable[Any],
        tracking_kwargs: Optional[TrackingKwargs] = None,
        orm_objs_pending_save: Optional[Sequence[Any]] = None,
        orm_objs_pending_delete: Optional[Sequence[Any]] = None,
    ) -> None:
        with self._rw_lock.gen_wlock():
            # Write event and notification records.
            for record in records:
                self._insert_record(record)

            if tracking_kwargs:
                # Write a tracking record.
                upstream_application_name = tracking_kwargs["upstream_application_name"]
                application_name = tracking_kwargs["application_name"]
                notification_id = tracking_kwargs["notification_id"]
                assert application_name == self.application_name, (
                    application_name,
                    self.application_name,
                )
                try:
                    app_tracking_records = self._all_tracking_records[application_name]
                except KeyError:
                    app_tracking_records = {}
                    self._all_tracking_records[
                        self.application_name
                    ] = app_tracking_records
                try:
                    upstream_tracking_records = app_tracking_records[
                        upstream_application_name
                    ]
                except KeyError:
                    upstream_tracking_records = set()
                    app_tracking_records[
                        upstream_application_name
                    ] = upstream_tracking_records

                if notification_id in upstream_tracking_records:
                    raise RecordConflictError(
                        (application_name, upstream_application_name, notification_id)
                    )
                upstream_tracking_records.add(notification_id)

    def _insert_record(self, sequenced_item: NamedTuple) -> None:
        position = getattr(sequenced_item, self.field_names.position)
        if not isinstance(position, int):
            raise NotImplementedError(
                "Popo record manager only supports sequencing with integers, "
                "but position was a {}".format(type(position))
            )

        sequence_id = getattr(sequenced_item, self.field_names.sequence_id)
        try:
            application_records = self._all_sequence_records[self.application_name]
        except KeyError:
            sequence_records: Dict[int, NamedTuple] = {}
            application_records = {sequence_id: sequence_records}
            self._all_sequence_records[self.application_name] = application_records
            self._all_sequence_max[self.application_name] = {}
        else:
            try:
                sequence_records = application_records[sequence_id]
            except KeyError:
                sequence_records = {}
                application_records[sequence_id] = sequence_records

        if position in sequence_records:
            raise RecordConflictError(position, len(sequence_records))

        if self.notification_id_name:
            # Just make sure we aren't making a gap in the sequence.
            if sequence_records:
                max_position = self._all_sequence_max[self.application_name][
                    sequence_id
                ]
                next_position = max_position + 1
            else:
                next_position = 0
            if position != next_position:
                raise AssertionError(
                    "Next position for sequence {} is {}, not {}".format(
                        sequence_id, next_position, position
                    )
                )

        sequence_records[position] = sequenced_item
        self._all_sequence_max[self.application_name][sequence_id] = position

        # Write a notification record.
        if self.notification_id_name:
            try:
                notification_records = self._all_notification_records[
                    self.application_name
                ]
            except KeyError:
                notification_records = {}
                self._all_notification_records[
                    self.application_name
                ] = notification_records

            next_notification_id = (self._get_max_record_id() or 0) + 1
            notification_records[next_notification_id] = {
                "notification_id": next_notification_id,
                "sequenced_item": sequenced_item,
            }
            self._all_notification_max[self.application_name] = next_notification_id

    def to_records(self, sequenced_items: Iterable[NamedTuple]) -> Iterable[Any]:
        return (PopoStoredEventRecord(s) for s in sequenced_items)


class PopoStoredEventRecord(object):
    """
    Encapsulates sequenced item tuple (containing real event object).

    Allows other attributes to be set, such as notification ID.
    """

    def __init__(self, sequenced_item: NamedTuple):
        self.sequenced_item = sequenced_item

    def __getattr__(self, item: str) -> Any:
        return getattr(self.sequenced_item, item)
