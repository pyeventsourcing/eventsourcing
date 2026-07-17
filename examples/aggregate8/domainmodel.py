from __future__ import annotations

from uuid import UUID

from eventsourcing.domain_new import event
from eventsourcing.pydantic.immutable import Immutable
from eventsourcing.pydantic.mutable import (
    PydanticAggregate,
    PydanticAggregateSnapshot,
    PydanticAggregateState,
)


class Trick(Immutable):
    name: str


class DogSnapshotState(PydanticAggregateState):
    name: str
    tricks: list[Trick]


class Dog(PydanticAggregate):
    class Snapshot(PydanticAggregateSnapshot):
        state: DogSnapshotState

    @event("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @event("TrickAdded")
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
