from __future__ import annotations

from eventsourcing.persistence import Transcoder
from eventsourcing.pydantic.immutable import PydanticDecision


class PydanticTranscoder(Transcoder[PydanticDecision]):
    def encode(self, decision: PydanticDecision) -> bytes:
        return decision.model_dump_json().encode()

    def decode(
        self, data: bytes, decision_class: type[PydanticDecision]
    ) -> PydanticDecision:
        return decision_class.model_validate_json(data.decode())
