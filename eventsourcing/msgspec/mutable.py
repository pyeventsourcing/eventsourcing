from __future__ import annotations

import typing
from abc import ABC
from typing import Any, override

import eventsourcing.domain
from eventsourcing.msgspec.immutable import (
    AggregateEvent,
    Decision,
    Immutable,
)


class Aggregate(eventsourcing.domain.Aggregate[Decision]):
    pass


class Slice(eventsourcing.domain.Slice[Decision], ABC):
    pass


class EnduringObject(eventsourcing.domain.EnduringObject[Decision]):
    pass


class Group(eventsourcing.domain.Group[Decision]):
    pass


class AggregateState(Immutable):
    pass


class MuetableAggregateSnapshot(Decision):
    state: Any

    @classmethod
    def take(cls, aggregate: Aggregate) -> AggregateEvent:
        type_of_snapshot_state = typing.get_type_hints(cls)["state"]
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("new_decisions")
        aggregate_id = aggregate_state.pop("id")
        aggregate_version = aggregate_state.pop("version")
        snapshot_state = type_of_snapshot_state(**aggregate_state)
        return AggregateEvent(
            decision=cls(state=snapshot_state),
            originator_id=aggregate_id,
            originator_version=aggregate_version,
        )

    @override
    def mutate[TState](self, obj: TState | None) -> TState | None:
        """Reconstructs the snapshotted :class:`Aggregate` object."""
        assert obj is not None
        for key in type(self.state).__struct_fields__:
            object.__setattr__(obj, key, getattr(self.state, key))
        return obj
