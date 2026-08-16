from __future__ import annotations

from abc import ABC
from typing import Any, Self, TypeVar, get_type_hints, override

from eventsourcing import domain
from eventsourcing.dataclasses.immutable import (
    Decision,
    Immutable,
)


class Aggregate(domain.Aggregate[Decision]):
    pass


class Slice(domain.Slice[Decision], ABC):
    pass


class EnduringObject(domain.EnduringObject[Decision]):
    pass


class Group(domain.Group[Decision]):
    pass


class AggregateState(Immutable):
    pass


_T = TypeVar("_T")


class AggregateSnapshot(Decision):
    state: Any

    @classmethod
    def take(cls, aggregate: Aggregate) -> Self:
        type_of_snapshot_state = get_type_hints(cls)["state"]
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("new_decisions")
        aggregate_state.pop("id")
        aggregate_state.pop("version")
        snapshot_state = type_of_snapshot_state(**aggregate_state)
        return cls(state=snapshot_state)

    @override
    def mutate(self, obj: _T | None) -> _T | None:
        """Reconstructs the snapshotted :class:`Aggregate` object."""
        assert obj is not None
        for key in type(self.state).__struct_fields__:
            object.__setattr__(obj, key, getattr(self.state, key))
        return obj
