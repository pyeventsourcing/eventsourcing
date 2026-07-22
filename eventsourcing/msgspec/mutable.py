from __future__ import annotations

import typing
from abc import ABC
from typing import Any, Generic, Self, TypeVar

from eventsourcing.domain import Aggregate, EnduringObject, Group, Slice
from eventsourcing.msgspec.immutable import (
    MsgspecDecision,
    MsgspecImmutable,
    TMsgspecDecision,
)


class MsgspecAggregate(Aggregate[TMsgspecDecision]):
    pass


class MsgspecSlice(Slice[TMsgspecDecision], ABC):
    pass


class MsgspecEnduringObject(EnduringObject[TMsgspecDecision]):
    pass


class MsgspecGroup(Group[TMsgspecDecision]):
    pass


class MsgspecAggregateState(MsgspecImmutable):
    pass


_T = TypeVar("_T")


class MsgspecAggregateSnapshot(MsgspecDecision, Generic[TMsgspecDecision]):
    state: Any

    @classmethod
    def take(cls, aggregate: MsgspecAggregate[TMsgspecDecision]) -> Self:
        type_of_snapshot_state = typing.get_type_hints(cls)["state"]
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("new_decisions")
        aggregate_state.pop("id")
        aggregate_state.pop("version")
        snapshot_state = type_of_snapshot_state(**aggregate_state)
        return cls(
            state=snapshot_state,
        )

    def mutate(self, obj: _T | None) -> _T | None:
        """Reconstructs the snapshotted :class:`Aggregate` object."""
        assert obj is not None
        for key in type(self.state).__struct_fields__:
            object.__setattr__(obj, key, getattr(self.state, key))
        return obj
