from __future__ import annotations

from eventsourcing.decorator import triggers
from eventsourcing.pydantic import Aggregate, Immutable


class Trick(Immutable):
    name: str


class Dog(Aggregate):
    @triggers("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[Trick] = []

    @triggers("TrickAdded")
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
