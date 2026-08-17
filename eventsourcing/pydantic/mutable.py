from __future__ import annotations

from typing import Any, get_type_hints, override

from pydantic import ConfigDict

import eventsourcing.domain
from eventsourcing.pydantic import AggregateEvent
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


class MutableAggregateSnapshot(Decision):
    state: Any

    @classmethod
    def take(cls, aggregate: Aggregate) -> AggregateEvent:
        type_of_snapshot_state = get_type_hints(cls)["state"]
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("new_decisions")
        aggregate_id = aggregate_state.pop("id")
        aggregate_version = aggregate_state.pop("version")
        snapshot_state = type_of_snapshot_state(**aggregate_state)
        decision = cls(state=snapshot_state)
        return AggregateEvent(
            decision=decision,
            originator_id=aggregate_id,
            originator_version=aggregate_version,
        )

    @override
    def mutate[TState](self, obj: TState | None) -> TState | None:
        """Reconstructs the snapshotted :class:`Aggregate` object."""
        assert obj is not None
        for key in self.state.__dict__:
            object.__setattr__(obj, key, getattr(self.state, key))
        return obj


class AggregateState(Immutable):
    model_config = ConfigDict(extra="allow")
