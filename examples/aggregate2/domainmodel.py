from __future__ import annotations

from eventsourcing.domain import triggers
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.mutable import PydanticAggregate


class Dog(PydanticAggregate):
    class Registered(PydanticDecision):
        name: str

    class TrickAdded(PydanticDecision):
        trick: str

    @triggers(Registered)
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[str] = []

    @triggers(TrickAdded)
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)
