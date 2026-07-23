from __future__ import annotations

import msgspec

import eventsourcing.persistence
from eventsourcing.msgspec.immutable import Decision


class Transcoder(eventsourcing.persistence.Transcoder[Decision]):
    def encode(self, decision: Decision) -> bytes:
        return msgspec.msgpack.encode(decision)

    def decode(self, data: bytes, decision_class: type[Decision]) -> Decision:
        return msgspec.msgpack.decode(data, type=decision_class)
