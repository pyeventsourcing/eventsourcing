from __future__ import annotations

from uuid import UUID

from eventsourcing.domain import event
from eventsourcing.msgspec.immutablemodel import Immutable
from eventsourcing.msgspec.mutablemodel import Aggregate, SnapshotState


class Trick(Immutable):
    name: str


class DogSnapshotState(SnapshotState):
    name: str
    tricks: list[Trick]


class Dog(Aggregate):
    @event("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @event("TrickAdded")
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)

    class Snapshot(Aggregate.Snapshot[UUID]):
        state: DogSnapshotState
