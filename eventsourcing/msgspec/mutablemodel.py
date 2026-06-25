from __future__ import annotations

import typing
from datetime import datetime  # noqa: TC003
from typing import Any, Self, cast
from uuid import UUID, uuid4

from eventsourcing.domain import (
    BaseAggregate,
    CanInitAggregate,
    CanMutateAggregate,
    CanSnapshotAggregate,
    MutableOrImmutableAggregate,
    TAggregate,
    TAggregateID,
)
from eventsourcing.msgspec.immutablemodel import (
    DomainEvent,
    Immutable,
)
from eventsourcing.utils import get_topic, resolve_topic


class SnapshotState(Immutable):
    created_on: datetime
    modified_on: datetime


class AggregateSnapshot(DomainEvent[TAggregateID], CanSnapshotAggregate[TAggregateID]):
    topic: str
    state: Any

    @classmethod
    def take(cls, aggregate: MutableOrImmutableAggregate[TAggregateID]) -> Self:
        type_of_snapshot_state = typing.get_type_hints(cls)["state"]
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("_id")
        aggregate_state.pop("_version")
        aggregate_state["created_on"] = aggregate_state.pop("_created_on")
        aggregate_state["modified_on"] = aggregate_state.pop("_modified_on")
        aggregate_state.pop("_pending_events")
        snapshot_state = type_of_snapshot_state(**aggregate_state)
        return cls(
            originator_id=aggregate.id,
            originator_version=aggregate.version,
            topic=get_topic(type(aggregate)),
            state=snapshot_state,
        )

    def mutate(self, aggregate: TAggregate | None) -> TAggregate | None:
        """Reconstructs the snapshotted :class:`Aggregate` object."""
        cls = cast("type[TAggregate]", resolve_topic(self.topic))
        aggregate_state: dict[str, Any] = {
            key: getattr(self.state, key) for key in type(self.state).__struct_fields__
        }
        aggregate_state["_id"] = self.originator_id
        aggregate_state["_version"] = self.originator_version
        aggregate_state["_created_on"] = self.state.created_on
        aggregate_state["_modified_on"] = self.state.modified_on
        aggregate_state["_version"] = self.originator_version
        aggregate_state["_pending_events"] = []
        aggregate = object.__new__(cls)
        object.__setattr__(aggregate, "__dict__", aggregate_state)
        return aggregate


class AggregateEvent(DomainEvent[TAggregateID], CanMutateAggregate[TAggregateID]):
    # class AggregateEvent(DomainEventY):
    def _as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__struct_fields__}


class Aggregate(BaseAggregate[UUID]):
    @classmethod
    def create_id(cls, *_: Any, **__: Any) -> UUID:
        return uuid4()

    class Event(AggregateEvent[UUID]):
        pass

    class Created(Event, CanInitAggregate[UUID]):
        originator_topic: str

    class Snapshot(Event, AggregateSnapshot[UUID]):
        pass


class AggregateStrID(BaseAggregate[str]):
    @classmethod
    def create_id(cls, *_: Any, **__: Any) -> str:
        return str(uuid4())

    class Event(AggregateEvent[str]):
        pass

    class Created(Event, CanInitAggregate[str]):
        originator_topic: str

    class Snapshot(Event, AggregateSnapshot[str]):
        pass
