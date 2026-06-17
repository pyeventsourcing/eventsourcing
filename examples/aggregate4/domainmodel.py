from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from eventsourcing.dispatch import singledispatchmethod
from examples.aggregate4.baseclasses import Aggregate, DomainEvent


@dataclass
class Dog(Aggregate):
    name: str
    tricks: list[str]

    @dataclass(frozen=True)
    class Registered(DomainEvent):
        name: str

    @dataclass(frozen=True)
    class TrickAdded(DomainEvent):
        trick: str

    @classmethod
    def register(cls, name: str) -> Dog:
        event = cls.Registered(
            originator_id=uuid4(),
            originator_version=1,
            name=name,
        )
        dog = cls.project_events(None, [event])
        dog.append_event(event)
        return dog

    def add_trick(self, trick: str) -> None:
        self.trigger_event(self.TrickAdded, trick=trick)

    @singledispatchmethod
    def apply_event(self, event: DomainEvent) -> None:
        super().apply_event(event)

    @apply_event.register(Registered)
    def _(self, event: Registered) -> None:
        self.id = event.originator_id
        self.version = event.originator_version
        self.created_on = event.timestamp
        self.modified_on = event.timestamp
        self.name = event.name
        self.tricks = []

    @apply_event.register(TrickAdded)
    def _(self, event: TrickAdded) -> None:
        self.tricks.append(event.trick)
        self.version = event.originator_version
        self.modified_on = event.timestamp
