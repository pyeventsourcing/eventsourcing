from __future__ import annotations

from typing import TYPE_CHECKING, List, cast

from eventsourcing.examples.cargoshipping.application import BookingApplication
from eventsourcing.examples.cargoshipping.domainmodel import Cargo
from eventsourcing.examples.searchabletimestamps.persistence import (
    SearchableTimestampsRecorder,
)

if TYPE_CHECKING:  # pragma: nocover
    from datetime import datetime
    from uuid import UUID

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.persistence import Recording


class SearchableTimestampsApplication(BookingApplication):
    def _record(self, processing_event: ProcessingEvent) -> List[Recording]:
        event_timestamps_data = [
            (e.originator_id, e.timestamp, e.originator_version)
            for e in processing_event.events
            if isinstance(e, Cargo.Event)
        ]
        processing_event.saved_kwargs["event_timestamps_data"] = event_timestamps_data
        return super()._record(processing_event)

    def get_cargo_at_timestamp(self, tracking_id: UUID, timestamp: datetime) -> Cargo:
        recorder = cast(SearchableTimestampsRecorder, self.recorder)
        version = recorder.get_version_at_timestamp(tracking_id, timestamp)
        return cast(Cargo, self.repository.get(tracking_id, version=version))
