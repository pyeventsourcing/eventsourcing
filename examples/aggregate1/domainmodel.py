from __future__ import annotations

from eventsourcing.domain_new import triggers
from eventsourcing.pydantic.immutable import Immutable
from eventsourcing.pydantic.mutable import PydanticAggregate


class Trick(Immutable):
    name: str


class Dog(PydanticAggregate):
    @triggers("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[str] = []

    @triggers("TrickAdded")
    def add_trick(self, trick: Trick) -> None:
        self.tricks.append(trick)
