from __future__ import annotations

from eventsourcing.domain import triggers
from eventsourcing.pydantic import Aggregate, Decision


class Dog(Aggregate):
    class Registered(Decision):
        name: str

    class TrickAdded(Decision):
        trick: str

    @triggers(Registered)
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[str] = []

    @triggers(TrickAdded)
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)
