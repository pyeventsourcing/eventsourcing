from __future__ import annotations

import eventsourcing.application
import eventsourcing.dcb.application
from eventsourcing.pydantic.immutable import Decision
from eventsourcing.pydantic.transcoder import Transcoder


class AggregatesApplication(eventsourcing.application.AggregatesApplication[Decision]):
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()


class DCBApplication(eventsourcing.dcb.application.DCBApplication[Decision]):
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()
