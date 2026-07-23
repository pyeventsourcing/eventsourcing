from __future__ import annotations

import eventsourcing.application
import eventsourcing.dcb.application
from eventsourcing.dataclasses.immutable import Decision
from eventsourcing.dataclasses.transcoder import Transcoder


class AggregatesApplication(eventsourcing.application.AggregatesApplication[Decision]):
    def construct_transcoder(self) -> eventsourcing.persistence.Transcoder[Decision]:
        return Transcoder()


class DCBApplication(eventsourcing.dcb.application.DCBApplication[Decision]):
    def construct_transcoder(self) -> eventsourcing.persistence.Transcoder[Decision]:
        return Transcoder()
