from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict

import eventsourcing.domain
from eventsourcing.utils import get_topic


class Immutable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PydanticDecision(Immutable, eventsourcing.domain.AbstractDecision):
    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ImmutablePydanticAggregate(Immutable):
    id: str
    version: int


class ImmutablePydanticAggregateSnapshot(PydanticDecision):
    topic: str
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: ImmutablePydanticAggregate) -> Self:
        return cls(
            topic=get_topic(type(aggregate)),
            state=aggregate.model_dump(),
        )
