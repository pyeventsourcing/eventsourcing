from __future__ import annotations

from dataclasses import dataclass
from functools import singledispatch
from uuid import uuid4

from examples.aggregate6.baseclasses import (
    Aggregate,
    DomainEvent,
    Snapshot,
    aggregate_projector,
)


@dataclass(frozen=True)
class Dog(Aggregate):
    name: str
    tricks: tuple[str, ...]


@dataclass(frozen=True)
class DogRegistered(DomainEvent):
    name: str


@dataclass(frozen=True)
class TrickAdded(DomainEvent):
    trick: str


def register_dog(name: str) -> DomainEvent:
    return DogRegistered(
        originator_id=uuid4(),
        originator_version=1,
        name=name,
    )


def add_trick(dog: Dog, trick: str) -> DomainEvent:
    return TrickAdded(
        originator_id=dog.id,
        originator_version=dog.version + 1,
        trick=trick,
    )


@singledispatch
def mutate_dog(_: DomainEvent, __: Dog | None) -> Dog | None:
    """Mutates aggregate with event."""


@mutate_dog.register
def _(event: DogRegistered, _: None) -> Dog:
    return Dog(
        id=event.originator_id,
        version=event.originator_version,
        created_on=event.timestamp,
        modified_on=event.timestamp,
        name=event.name,
        tricks=(),
    )


@mutate_dog.register
def _(event: TrickAdded, dog: Dog) -> Dog:
    return Dog(
        id=dog.id,
        version=event.originator_version,
        created_on=dog.created_on,
        modified_on=event.timestamp,
        name=dog.name,
        tricks=(*dog.tricks, event.trick),
    )


@mutate_dog.register
def _(event: Snapshot, _: None) -> Dog:
    return Dog(
        id=event.state["id"],
        version=event.state["version"],
        created_on=event.state["created_on"],
        modified_on=event.state["modified_on"],
        name=event.state["name"],
        tricks=tuple(event.state["tricks"]),  # comes back from JSON as a list
    )


project_dog = aggregate_projector(mutate_dog)
