from __future__ import annotations

import typing
from typing import Any, Self, TypeVar

from eventsourcing.dataclasses.immutable import (
    DataclassDecision,
    Immutable,
)
from eventsourcing.domain_new import Aggregate


class DataclassAggregate(Aggregate[DataclassDecision]):
    pass


class SnapshotState(Immutable):
    pass


_T = TypeVar("_T")


class AggregateSnapshot(DataclassDecision):
    state: Any

    @classmethod
    def take(cls, aggregate: DataclassAggregate) -> Self:
        type_of_snapshot_state = typing.get_type_hints(cls)["state"]
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("new_decisions")
        aggregate_state.pop("id")
        aggregate_state.pop("version")
        snapshot_state = type_of_snapshot_state(**aggregate_state)
        return cls(state=snapshot_state)

    def mutate(self, aggregate: _T | None) -> _T | None:
        """Reconstructs the snapshotted :class:`Aggregate` object."""
        assert aggregate is not None
        for key in type(self.state).__struct_fields__:
            object.__setattr__(aggregate, key, getattr(self.state, key))
        return aggregate
