from __future__ import annotations

from typing import override

import msgspec

import eventsourcing.persistence
from eventsourcing.msgspec.immutable import Decision


class Transcoder(eventsourcing.persistence.Transcoder[Decision]):
    @override
    def encode(self, decision: Decision) -> bytes:
        return msgspec.msgpack.encode(decision)

    @override
    def decode(self, data: bytes, decision_class: type[Decision]) -> Decision:
        return msgspec.msgpack.decode(data, type=decision_class)
