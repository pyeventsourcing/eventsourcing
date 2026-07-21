from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import AggregatesApplication
from eventsourcing.dcb.application import DCBApplication
from eventsourcing.msgspec.immutable import MsgspecDecision
from eventsourcing.msgspec.transcoder import MsgspecTranscoder

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class MsgspecAggregatesApplication(AggregatesApplication[MsgspecDecision]):
    def construct_transcoder(self) -> Transcoder[MsgspecDecision]:
        return MsgspecTranscoder()


class MsgspecDCBApplication(DCBApplication[MsgspecDecision]):
    def construct_transcoder(self) -> Transcoder[MsgspecDecision]:
        return MsgspecTranscoder()
