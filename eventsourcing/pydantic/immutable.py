from __future__ import annotations

from typing import Any, Self, override

from pydantic import BaseModel, ConfigDict

import eventsourcing.domain


class Immutable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Decision(Immutable, eventsourcing.domain.Decision):
    @override
    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ImmutableAggregate(Immutable):
    id: str
    version: int


class ImmutableAggregateSnapshot(Decision):
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: ImmutableAggregate) -> Self:
        return cls(
            state=aggregate.model_dump(),
        )
