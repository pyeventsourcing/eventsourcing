from __future__ import annotations

import msgspec

from eventsourcing.msgspec.immutable import TMsgspecDecision
from eventsourcing.persistence import Transcoder


class MsgspecTranscoder(Transcoder[TMsgspecDecision]):
    def encode(self, decision: TMsgspecDecision) -> bytes:
        return msgspec.msgpack.encode(decision)

    def decode(
        self, data: bytes, decision_class: type[TMsgspecDecision]
    ) -> TMsgspecDecision:
        return msgspec.msgpack.decode(data, type=decision_class)
