from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from eventsourcing.application import AggregateNotFoundError
from eventsourcing.domain import StreamEvent
from examples.cargoshipping.application import BookingApplication
from examples.cargoshipping.domainmodel import Cargo, CargoEvent
from examples.searchabletimestamps.persistence import SearchableTimestampsRecorder

if TYPE_CHECKING:
    from datetime import datetime

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.pydantic import Decision


class CargoNotFoundError(AggregateNotFoundError):
    pass


class SearchableTimestampsApplication(BookingApplication):
    @override
    def _record(self, processing_event: ProcessingEvent[Decision]) -> int | None:
        event_timestamps_data = [
            (
                e.stream_id,
                e.stream_position,
                e.decision.timestamp,
            )
            for e in processing_event.events
            if isinstance(e, StreamEvent) and isinstance(e.decision, CargoEvent)
        ]
        processing_event.saved_kwargs["event_timestamps_data"] = event_timestamps_data
        return super()._record(processing_event)

    def get_cargo_at_timestamp(self, tracking_id: str, timestamp: datetime) -> Cargo:
        recorder = cast(SearchableTimestampsRecorder, self.recorder)
        version = recorder.get_version_at_timestamp(tracking_id, timestamp)
        if version is None:
            raise CargoNotFoundError((tracking_id, timestamp))
        return self.repository.get(tracking_id, Cargo, version=version)
