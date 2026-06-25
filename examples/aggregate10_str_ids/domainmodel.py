from __future__ import annotations

from eventsourcing.domain import event
from eventsourcing.msgspec.immutablemodel import Immutable
from eventsourcing.msgspec.mutablemodel import (
    AggregateStrID,
    SnapshotState,
)


class Trick(Immutable):
    name: str


class DogSnapshotState(SnapshotState):
    name: str
    tricks: list[Trick]


class Dog(AggregateStrID):
    @event("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @event("TrickAdded")
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)

    class Snapshot(AggregateStrID.Snapshot):
        state: DogSnapshotState
