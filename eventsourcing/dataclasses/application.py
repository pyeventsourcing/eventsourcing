from __future__ import annotations

from typing import override

import eventsourcing.application
import eventsourcing.dcb.application
import eventsourcing.system
from eventsourcing.dataclasses.immutable import Decision
from eventsourcing.dataclasses.transcoder import Transcoder


class AggregatesApplication(eventsourcing.application.AggregatesApplication[Decision]):
    @override
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()


class ProcessApplication(eventsourcing.system.ProcessApplication[Decision]):
    @override
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()


class DcbApplication(eventsourcing.dcb.application.DcbApplication[Decision]):
    @override
    def construct_transcoder(self) -> Transcoder:
        return Transcoder()
