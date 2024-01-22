from __future__ import annotations

from typing import List, cast

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import Aggregate


class Dog(Aggregate):
    class Event(Aggregate.Event):
        def apply(self, aggregate: Aggregate) -> None:
            cast(Dog, aggregate).apply(self)

    class Registered(Event, Aggregate.Created):
        name: str

    class TrickAdded(Event):
        trick: str

    @classmethod
    def register(cls, name: str) -> Dog:
        return cls._create(cls.Registered, name=name)

    def add_trick(self, trick: str) -> None:
        self.trigger_event(self.TrickAdded, trick=trick)

    @singledispatchmethod
    def apply(self, event: Event) -> None:
        """Applies event to aggregate."""

    @apply.register
    def _(self, event: Dog.Registered) -> None:
        self.name = event.name
        self.tricks: List[str] = []

    @apply.register
    def _(self, event: Dog.TrickAdded) -> None:
        self.tricks.append(event.trick)
