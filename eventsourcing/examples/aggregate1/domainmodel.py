from __future__ import annotations

from typing import List

from eventsourcing.domain import Aggregate, event


class Dog(Aggregate):
    @event("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: List[str] = []

    @event("TrickAdded")
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)
