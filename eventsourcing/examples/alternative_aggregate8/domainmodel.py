from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel

from eventsourcing.domain import (
    Aggregate,
    CanInitAggregate,
    CanMutateAggregate,
    CanSnapshot,
    event,
)


class DomainEvent(BaseModel):
    originator_id: UUID
    originator_version: int
    timestamp: datetime

    class Config:
        allow_mutation = False


class BaseAggregate(Aggregate):
    class Event(DomainEvent, CanMutateAggregate[Aggregate]):
        pass

    class Created(Event, CanInitAggregate[Aggregate]):
        originator_topic: str


class Snapshot(DomainEvent, CanSnapshot[BaseAggregate]):
    topic: str
    state: Dict[str, Any]


class Dog(BaseAggregate):
    @event("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: List[str] = []

    class TrickAdded(BaseAggregate.Event):
        trick: str

    @event(TrickAdded)
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)
