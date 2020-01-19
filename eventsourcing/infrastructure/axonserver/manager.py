from typing import Any, Optional, Iterable, Sequence, NamedTuple, Dict
from uuid import UUID, uuid4

from axonclient.client import AxonClient, AxonEvent

from eventsourcing.infrastructure.base import BaseRecordManager


class AxonRecordManager(BaseRecordManager):
    def __init__(self, axon_client: AxonClient, *args: Any, **kwargs: Any):
        super(AxonRecordManager, self).__init__(*args, **kwargs)
        self.axon_client = axon_client

    def all_sequence_ids(self):
        return []

    def delete_record(self, record: Any) -> None:
        raise NotImplemented()

    def get_notifications(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Iterable:
        pass

    def get_record(self, sequence_id: UUID, position: int) -> Any:
        raise NotImplemented()

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

        if self.record_class == 'snapshot_records':
            # Todo: This isn't actually working. But we don't need it.
            # events = self.axon_client.list_snapshot_events(
            #     aggregate_id=sequence_id,
            #     initial_sequence=initial_sequence_number,
            #     max_sequence=None,
            #     max_reults=None,
            # )
            events = []
        else:
            events = self.axon_client.list_aggregate_events(
                aggregate_id=sequence_id,
                initial_sequence=initial_sequence_number,
                allow_snapshots=True,
            )
        if limit:
            if query_ascending:
                events = events[:limit]
            else:
                events = events[-limit:]
        if query_ascending != results_ascending:
            events = reversed(events)
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
        is_snapshot = payload_type.endswith('#Snapshot')
        return AxonEvent(
            message_identifier=message_identifier,
            aggregate_identifier=sequence_id,
            aggregate_sequence_number=aggregate_sequence_number,
            aggregate_type='AggregateRoot',
            timestamp=1,
            payload_type=payload_type,
            payload_revision='1',
            payload_data=payload_data,
            snapshot=is_snapshot,
            meta_data={}
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
            self.axon_client.append_event(records)

    def get_field_kwargs(self, item: object) -> Dict[str, Any]:
        assert isinstance(item, AxonEvent)
        return {
            self.field_names.sequence_id: UUID(item.aggregate_identifier),
            self.field_names.position: item.aggregate_sequence_number,
            self.field_names.topic: item.payload_type,
            self.field_names.state: item.payload_data,
        }
