from __future__ import annotations

from eventsourcing.domain import event
from eventsourcing.msgspec import (
    Aggregate,
    AggregateSnapshot,
    AggregateState,
    Decision,
    Immutable,
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

    class Snapshot(AggregateSnapshot):
        state: DogSnapshotState

    @event(Registered)
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @event(TrickAdded)
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
