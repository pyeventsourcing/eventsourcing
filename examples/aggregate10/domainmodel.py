from __future__ import annotations

from eventsourcing.decorator import event
from eventsourcing.msgspec import (
    Aggregate,
    AggregateState,
    Decision,
    Immutable,
    MuetableAggregateSnapshot,
)


class Trick(Immutable):
    name: str


class DogSnapshotState(AggregateState):
    name: str
    tricks: list[Trick]


class Dog(Aggregate):
    class Registered(Decision):
        name: str

    class TrickAdded(Decision):
        trick: Trick

    class Snapshot(MuetableAggregateSnapshot):
        state: DogSnapshotState

    @event(Registered)
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @event(TrickAdded)
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
