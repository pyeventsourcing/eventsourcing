from __future__ import annotations

import typing
from typing import Any, Self, TypeVar

from pydantic import ConfigDict

import eventsourcing.domain
from eventsourcing.pydantic.immutable import (
    Decision,
    Immutable,
)


class Aggregate(eventsourcing.domain.Aggregate[Decision]):
    pass


class Slice(eventsourcing.domain.Slice[Decision]):
    pass


class EnduringObject(eventsourcing.domain.EnduringObject[Decision]):
    pass


class Group(eventsourcing.domain.Group[Decision]):
    pass


_T = TypeVar("_T")


class AggregateSnapshot(Decision):
    state: Any

    @classmethod
    def take(cls, aggregate: Aggregate) -> Self:
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


class AggregateState(Immutable):
    model_config = ConfigDict(extra="allow")
