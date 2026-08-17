from __future__ import annotations

from typing import override

import eventsourcing.application
import eventsourcing.dcb.application
import eventsourcing.projection
import eventsourcing.system
from eventsourcing.application import SupportsTranscoding
from eventsourcing.dataclasses.immutable import Decision
from eventsourcing.dataclasses.transcoder import Transcoder


class WithTranscoder(SupportsTranscoding[Decision]):
    @override
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()


class AggregatesApplication(
    WithTranscoder, eventsourcing.application.AggregatesApplication[Decision]
):
    pass


class EventSourcedProjection(
    WithTranscoder, eventsourcing.projection.EventSourcedEventProcessor[Decision]
):
    pass


class ProcessApplication(
    WithTranscoder, eventsourcing.system.ProcessApplication[Decision]
):
    pass


class DcbApplication(
    WithTranscoder, eventsourcing.dcb.application.DcbApplication[Decision]
):
    pass
