from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import ProgrammingError
from examples.aggregate5.baseclasses import Aggregate, DomainEvent


@dataclass(frozen=True)
class Dog(Aggregate):
    name: str
    tricks: tuple[str, ...]

    @dataclass(frozen=True)
    class Registered(DomainEvent):
        name: str

    @dataclass(frozen=True)
    class TrickAdded(DomainEvent):
        trick: str

    @staticmethod
    def register(name: str) -> tuple[Dog, DomainEvent]:
        event = Dog.Registered(
            originator_id=uuid4(),
            originator_version=1,
            name=name,
        )
        dog = Dog.mutate(event, None)
        return dog, event

    def add_trick(self, trick: str) -> tuple[Dog, DomainEvent]:
        event = self.trigger_event(Dog.TrickAdded, trick=trick)
        dog = Dog.mutate(event, self)
        return dog, event

    @singledispatchmethod
    @staticmethod
    def mutate(event: DomainEvent, aggregate: Dog | None) -> Dog:  # noqa: ARG004
        """Mutates aggregate with event."""
        msg = f"Event type not supported: {type(event)}"
        raise ProgrammingError(msg)

    @mutate.register
    @staticmethod
    def _(event: Dog.Registered, _: Dog | None) -> Dog:
        return Dog(
            id=event.originator_id,
            version=event.originator_version,
            created_on=event.timestamp,
            modified_on=event.timestamp,
            name=event.name,
            tricks=(),
        )

    @mutate.register
    @staticmethod
    def _(event: Dog.TrickAdded, aggregate: Dog | None) -> Dog:
        assert aggregate is not None
        return Dog(
            id=aggregate.id,
            version=event.originator_version,
            created_on=aggregate.created_on,
            modified_on=event.timestamp,
            name=aggregate.name,
            tricks=(*aggregate.tricks, event.trick),
        )

    @mutate.register
    @staticmethod
    def _(event: Dog.Snapshot, _: Dog | None) -> Dog:
        return Dog(
            id=event.state["id"],
            version=event.state["version"],
            created_on=event.state["created_on"],
            modified_on=event.state["modified_on"],
            name=event.state["name"],
            tricks=tuple(event.state["tricks"]),  # comes back from JSON as a list
        )
