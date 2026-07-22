from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import AggregatesApplication
from eventsourcing.dcb.application import DCBApplication
from eventsourcing.msgspec.immutable import TMsgspecDecision
from eventsourcing.msgspec.transcoder import MsgspecTranscoder

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class MsgspecAggregatesApplication(AggregatesApplication[TMsgspecDecision]):
    def construct_transcoder(self) -> Transcoder[TMsgspecDecision]:
        return MsgspecTranscoder()


class MsgspecDCBApplication(DCBApplication[TMsgspecDecision]):
    def construct_transcoder(self) -> Transcoder[TMsgspecDecision]:
        return MsgspecTranscoder()
