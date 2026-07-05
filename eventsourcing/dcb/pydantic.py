from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

import eventsourcing.dcb.domain
from eventsourcing.dcb.persistence import DCBMapper


class Decision(BaseModel, eventsourcing.dcb.domain.Decision):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class PydanticMapper(DCBMapper[Decision]):
    def _to_data(self, decision: Decision) -> bytes:
        return decision.model_dump_json().encode()

    def _to_decision(self, data: bytes, decision_class: type[Decision]) -> Decision:
        return decision_class.model_validate_json(data.decode())
