from __future__ import annotations

import eventsourcing.application
import eventsourcing.dcb.application
from eventsourcing.msgspec.immutable import Decision
from eventsourcing.msgspec.transcoder import Transcoder


class AggregatesApplication(eventsourcing.application.AggregatesApplication[Decision]):
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()


class DCBApplication(eventsourcing.dcb.application.DCBApplication[Decision]):
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()
