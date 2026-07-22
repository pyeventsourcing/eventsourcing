from __future__ import annotations

from eventsourcing.persistence import Transcoder
from eventsourcing.pydantic.immutable import TPydanticDecision


class PydanticTranscoder(Transcoder[TPydanticDecision]):
    def encode(self, decision: TPydanticDecision) -> bytes:
        return decision.model_dump_json().encode()

    def decode(
        self, data: bytes, decision_class: type[TPydanticDecision]
    ) -> TPydanticDecision:
        return decision_class.model_validate_json(data.decode())
