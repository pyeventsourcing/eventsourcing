from __future__ import annotations

from eventsourcing.domain import event
from eventsourcing.pydantic.immutablemodel import Immutable
from eventsourcing.pydantic.mutablemodel import (
    Aggregate,
    AggregateSnapshot,
    SnapshotState,
)


class Trick(Immutable):
    name: str


class DogSnapshotState(SnapshotState):
    name: str
    tricks: list[Trick]


class Dog(Aggregate[str]):
    class Snapshot(AggregateSnapshot[str]):
        state: DogSnapshotState

    class Event(Aggregate.Event[str]):
        pass

    class Registered(Aggregate.Created[str]):
        name: str

    class TrickAdded(Event):
        trick: Trick

    @event(Registered)
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @event(TrickAdded)
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
