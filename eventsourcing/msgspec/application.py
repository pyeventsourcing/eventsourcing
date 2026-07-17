from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import Application
from eventsourcing.msgspec.immutable import MsgspecDecision
from eventsourcing.msgspec.transcoder import MsgspecTranscoder

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class MsgspecApplication(Application[MsgspecDecision]):
    def construct_transcoder(self) -> Transcoder[MsgspecDecision]:
        return MsgspecTranscoder()
