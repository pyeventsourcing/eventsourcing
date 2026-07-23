from __future__ import annotations

import eventsourcing.persistence
from eventsourcing.pydantic.immutable import Decision


class Transcoder(eventsourcing.persistence.Transcoder[Decision]):
    def encode(self, decision: Decision) -> bytes:
        return decision.model_dump_json().encode()

    def decode(self, data: bytes, decision_class: type[Decision]) -> Decision:
        return decision_class.model_validate_json(data.decode())
