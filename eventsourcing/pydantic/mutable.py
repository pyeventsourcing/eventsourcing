from __future__ import annotations

import typing
from typing import Any, Generic, Self, TypeVar

from pydantic import ConfigDict

from eventsourcing.domain import Aggregate, EnduringObject, Group, Slice
from eventsourcing.pydantic.immutable import (
    PydanticDecision,
    PydanticImmutable,
    TPydanticDecision,
)


class PydanticAggregate(Aggregate[TPydanticDecision]):
    pass


class PydanticSlice(Slice[TPydanticDecision]):
    pass


class PydanticEnduringObject(EnduringObject[TPydanticDecision]):
    pass


class PydanticGroup(Group[TPydanticDecision]):
    pass


_T = TypeVar("_T")


class PydanticAggregateSnapshot(PydanticDecision, Generic[TPydanticDecision]):
    state: Any

    @classmethod
    def take(cls, aggregate: PydanticAggregate[TPydanticDecision]) -> Self:
        type_of_snapshot_state = typing.get_type_hints(cls)["state"]
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("new_decisions")
        aggregate_state.pop("id")
        aggregate_state.pop("version")
        snapshot_state = type_of_snapshot_state(**aggregate_state)
        return cls(state=snapshot_state)

    def mutate(self, obj: _T | None) -> _T | None:
        """Reconstructs the snapshotted :class:`Aggregate` object."""
        assert obj is not None
        for key in self.state.__dict__:
            object.__setattr__(obj, key, getattr(self.state, key))
        return obj


class PydanticAggregateState(PydanticImmutable):
    model_config = ConfigDict(extra="allow")
