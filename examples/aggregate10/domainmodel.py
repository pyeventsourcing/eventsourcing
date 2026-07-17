from __future__ import annotations

from eventsourcing.domain_new import event
from eventsourcing.msgspec.immutable import Immutable, MsgspecDecision
from eventsourcing.msgspec.mutable import (
    MsgspecAggregate,
    MsgspecSnapshot,
    SnapshotState,
)


class Trick(Immutable):
    name: str


class DogSnapshotState(SnapshotState):
    name: str
    tricks: list[Trick]


class Dog(MsgspecAggregate):
    class Registered(MsgspecDecision):
        name: str

    class TrickAdded(MsgspecDecision):
        trick: Trick

    class Snapshot(MsgspecSnapshot):
        state: DogSnapshotState

    @event(Registered)
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @event(TrickAdded)
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
