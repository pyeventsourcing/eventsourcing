from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict
from typing_extensions import TypeVar

import eventsourcing.domain


class PydanticImmutable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PydanticDecision(PydanticImmutable, eventsourcing.domain.AbstractDecision):
    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


TPydanticDecision = TypeVar(
    "TPydanticDecision", bound=PydanticDecision, default=PydanticDecision
)


class PydanticImmutableAggregate(PydanticImmutable):
    id: str
    version: int


class PydanticImmutableAggregateSnapshot(PydanticDecision):
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: PydanticImmutableAggregate) -> Self:
        return cls(
            state=aggregate.model_dump(),
        )
