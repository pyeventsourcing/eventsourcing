from __future__ import annotations

import msgspec

from eventsourcing.msgspec.immutable import MsgspecDecision
from eventsourcing.persistence import Transcoder


class MsgspecTranscoder(Transcoder[MsgspecDecision]):
    def encode(self, decision: MsgspecDecision) -> bytes:
        return msgspec.msgpack.encode(decision)

    def decode(
        self, data: bytes, decision_class: type[MsgspecDecision]
    ) -> MsgspecDecision:
        return msgspec.msgpack.decode(data, type=decision_class)
