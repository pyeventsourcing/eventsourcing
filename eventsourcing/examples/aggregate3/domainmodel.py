from typing import List, cast

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import Aggregate


class Dog(Aggregate):
    class Registered(Aggregate.Created):
        name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: List[str] = []

    class Event(Aggregate.Event):
        def apply(self, aggregate: Aggregate) -> None:
            cast(Dog, aggregate).apply(self)

    @singledispatchmethod
    def apply(self, event: Event) -> None:
        pass

    class TrickAdded(Aggregate.Event):
        trick: str

    def add_trick(self, trick: str) -> None:
        self.trigger_event(self.TrickAdded, trick=trick)

    @apply.register
    def _(self, event: TrickAdded) -> None:
        self.tricks.append(event.trick)
