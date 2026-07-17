from __future__ import annotations

import typing
from typing import Any, Self, TypeVar

from pydantic import ConfigDict

from eventsourcing.domain_new import Aggregate
from eventsourcing.pydantic.immutable import Immutable, PydanticDecision


class PydanticAggregate(Aggregate[PydanticDecision]):
    pass


_T = TypeVar("_T")


class PydanticAggregateSnapshot(PydanticDecision):
    state: Any

    @classmethod
    def take(cls, aggregate: PydanticAggregate) -> Self:
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
        for key in self.state.__dict__:
            object.__setattr__(aggregate, key, getattr(self.state, key))
        return aggregate


class PydanticAggregateState(Immutable):
    model_config = ConfigDict(extra="allow")
