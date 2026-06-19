from __future__ import annotations

from typing import TYPE_CHECKING, cast

from eventsourcing.application import AggregateNotFoundError
from examples.cargoshipping.application import BookingApplication
from examples.cargoshipping.domainmodel import Cargo

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.persistence import Recording
    from examples.searchabletimestamps.persistence import SearchableTimestampsRecorder


class CargoNotFoundError(AggregateNotFoundError):
    pass


class SearchableTimestampsApplication(BookingApplication):
    def _record(self, processing_event: ProcessingEvent) -> list[Recording]:
        event_timestamps_data = [
            (e.originator_id, e.timestamp, e.originator_version)
            for e in processing_event.events
            if isinstance(e, Cargo.Event)
        ]
        processing_event.saved_kwargs["event_timestamps_data"] = event_timestamps_data
        return super()._record(processing_event)

    def get_cargo_at_timestamp(self, tracking_id: UUID, timestamp: datetime) -> Cargo:
        recorder = cast("SearchableTimestampsRecorder", self.recorder)
        version = recorder.get_version_at_timestamp(tracking_id, timestamp)
        if version is None:
            raise CargoNotFoundError((tracking_id, timestamp))
        return cast("Cargo", self.repository.get(tracking_id, version=version))
