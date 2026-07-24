from __future__ import annotations

import eventsourcing.application
import eventsourcing.dcb.application
from eventsourcing.dataclasses.immutable import Decision
from eventsourcing.dataclasses.transcoder import Transcoder


class AggregatesApplication(eventsourcing.application.AggregatesApplication[Decision]):
    def construct_transcoder(self) -> eventsourcing.persistence.Transcoder[Decision]:
        return Transcoder()


class DcbApplication(eventsourcing.dcb.application.DcbApplication[Decision]):
    def construct_transcoder(self) -> eventsourcing.persistence.Transcoder[Decision]:
        return Transcoder()
