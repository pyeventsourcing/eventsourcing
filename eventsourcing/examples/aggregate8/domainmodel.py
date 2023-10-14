from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Extra

from eventsourcing.domain import (
    Aggregate as BaseAggregate,
    CanInitAggregate,
    CanMutateAggregate,
    CanSnapshotAggregate,
    event,
)


class DomainEvent(BaseModel):
    originator_id: UUID
    originator_version: int
    timestamp: datetime

    class Config:
        allow_mutation = False


class Aggregate(BaseAggregate):
    class Event(DomainEvent, CanMutateAggregate):
        pass

    class Created(Event, CanInitAggregate):
        originator_topic: str


class SnapshotState(BaseModel):
    class Config:
        extra = Extra.allow


class AggregateSnapshot(DomainEvent, CanSnapshotAggregate):
    topic: str
    state: SnapshotState


class Trick(BaseModel):
    name: str


class DogState(SnapshotState):
    name: str
    tricks: List[Trick]


class Dog(Aggregate):
    class Snapshot(AggregateSnapshot):
        state: DogState

    @event("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: List[Trick] = []

    @event("TrickAdded")
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
