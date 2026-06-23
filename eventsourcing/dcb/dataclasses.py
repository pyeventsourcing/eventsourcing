from dataclasses import dataclass, field
from typing import Any

from eventsourcing.dcb import domain
from eventsourcing.domain import get_metadata_from_context


@dataclass(kw_only=True)
class Decision(domain.Decision):
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()
