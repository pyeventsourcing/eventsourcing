from __future__ import annotations

from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.mutable import PydanticAggregate


class Dog(PydanticAggregate):
    class Event(PydanticDecision):
        def apply(self, aggregate: Dog) -> None:
            aggregate.apply(self)

    class Registered(Event):
        name: str

    class TrickAdded(Event):
        trick: str

    def __init__(self):
        self.name: str = ""
        self.tricks: list[str] = []

    @classmethod
    def register(cls, name: str) -> Dog:
        dog = Dog._create()
        dog.trigger_event(cls.Registered, name=name)
        return dog

    def add_trick(self, trick: str) -> None:
        self.trigger_event(self.TrickAdded, trick=trick)

    def apply(self, decision: Event) -> None:
        """Applies event to aggregate."""
        match decision:
            case Dog.Registered(name=name):
                self.name = name
                self.tricks = []
            case Dog.TrickAdded(trick=trick):
                self.tricks.append(trick)
