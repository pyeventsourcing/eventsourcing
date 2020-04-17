from typing import Any, Dict, Iterable, NamedTuple, Optional, Sequence
from uuid import UUID, uuid4

from axonclient.client import AxonClient, AxonEvent
from axonclient.exceptions import OutOfRangeError
from google.protobuf.internal.wire_format import INT32_MAX

from eventsourcing.infrastructure.base import RecordManagerWithNotifications


class AxonNotification(object):
    def __init__(self, tracking_token, axon_event: AxonEvent):
        self.tracking_token = tracking_token
        self.axon_event = axon_event
        self.originator_id = UUID(axon_event.aggregate_identifier)
        self.originator_version = axon_event.aggregate_sequence_number
        self.topic = axon_event.payload_type
        self.state = axon_event.payload_data

    @property
    def id(self):
        return self.tracking_token + 1


class AxonRecordManager(RecordManagerWithNotifications):
    has_integrated_snapshots = True
    can_limit_get_records = False
    can_lt_lte_get_records = False
    can_list_sequence_ids = False
    can_delete_records = False

    def __init__(self, axon_client: AxonClient, *args: Any, **kwargs: Any):
        super(AxonRecordManager, self).__init__(*args, **kwargs)
        self.axon_client = axon_client
        self.contiguous_record_ids = True
        self.notification_id_name = "id"

    def all_sequence_ids(self):
        return []

    def delete_record(self, record: Any) -> None:
        raise NotImplemented()

    def get_max_notification_id(self) -> int:
        return self.axon_client.get_last_token() + 1

    def get_notification_records(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Iterable:
        start = start or 0
        stop = stop or INT32_MAX
        number_of_permits = min(stop - start, INT32_MAX)
        events = self.axon_client.iter_events(
            tracking_token=start, number_of_permits=number_of_permits
        )
        for tracking_token, event in events:
            yield AxonNotification(tracking_token, axon_event=event)

    def get_record(self, sequence_id: UUID, position: int) -> Any:
        records = list(self.get_records(sequence_id, gte=position))
        if len(records):
            return records[0]
        else:
            self.raise_index_error(position)

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
        if gt is not None:
            initial_sequence_number = gt + 1
        elif gte is not None:
            initial_sequence_number = gte
        else:
            initial_sequence_number = 0

        events = self.axon_client.iter_aggregate_events(
            aggregate_id=str(sequence_id),
            initial_sequence=initial_sequence_number,
            allow_snapshots=True,
        )

        # if limit:
        #     if query_ascending:
        #         events = events[:limit]
        #     else:
        #         events = events[-limit:]

        if not results_ascending:
            events = reversed(list(events))

        return events

    def record_items(self, sequenced_items: Iterable[NamedTuple]) -> None:
        # Convert sequenced item(s) to database record(s).
        records = self.to_axon_events(sequenced_items)

        # Write records.
        self.write_records(records)

    def to_axon_events(self, items):
        for item in items:
            yield self.to_axon_event(item)

    def to_axon_event(self, item):
        message_identifier = str(uuid4())
        sequence_id = str(getattr(item, self.field_names.sequence_id))
        aggregate_sequence_number = getattr(item, self.field_names.position)
        payload_type = getattr(item, self.field_names.topic)
        payload_data = getattr(item, self.field_names.state)
        is_snapshot = payload_type.endswith("#Snapshot")
        return AxonEvent(
            message_identifier=message_identifier,
            aggregate_identifier=sequence_id,
            aggregate_sequence_number=aggregate_sequence_number,
            aggregate_type="AggregateRoot",
            timestamp=0,
            payload_type=payload_type,
            payload_revision="1",
            payload_data=payload_data,
            snapshot=is_snapshot,
            meta_data={},
        )

    def write_records(self, records):
        records = list(records)
        all_snapshots = all([r.snapshot for r in records])
        any_snapshots = any([r.snapshot for r in records])
        if any_snapshots:
            assert len(records) == 1, "Can't write more than one snapshot at once"
            if all_snapshots:
                self.axon_client.append_snapshot(records[0])
            else:
                raise AssertionError("Can't write events with snapshots")
        else:
            try:
                self.axon_client.append_event(records)
            except OutOfRangeError as e:
                self.raise_sequenced_item_conflict(e)

    def get_field_kwargs(self, item: object) -> Dict[str, Any]:
        assert isinstance(item, AxonEvent), item
        return {
            self.field_names.sequence_id: UUID(item.aggregate_identifier),
            self.field_names.position: item.aggregate_sequence_number,
            self.field_names.topic: item.payload_type,
            self.field_names.state: item.payload_data,
        }
