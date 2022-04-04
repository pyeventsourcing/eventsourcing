from __future__ import annotations

from typing import List

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import Aggregate


class Dog(Aggregate):
    class Registered(Aggregate.Created["Dog"]):
        name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: List[str] = []

    class Event(Aggregate.Event["Dog"]):
        def apply(self, aggregate: Dog) -> None:
            aggregate.apply(self)

    @singledispatchmethod
    def apply(self, event: Event) -> None:
        pass

    class TrickAdded(Aggregate.Event["Dog"]):
        trick: str

    def add_trick(self, trick: str) -> None:
        self.trigger_event(self.TrickAdded, trick=trick)

    @apply.register(TrickAdded)
    def _(self, event: TrickAdded) -> None:
        self.tricks.append(event.trick)
