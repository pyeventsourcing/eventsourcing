from __future__ import annotations

from functools import singledispatch
from uuid import uuid4

from examples.aggregate7.immutablemodel import (
    Aggregate,
    DomainEvent,
    Immutable,
    Snapshot,
    aggregate_projector,
)


class Trick(Immutable):
    name: str


class Dog(Aggregate):
    name: str
    tricks: tuple[Trick, ...]


class DogRegistered(DomainEvent):
    name: str


class TrickAdded(DomainEvent):
    trick: Trick


def register_dog(name: str) -> DomainEvent:
    return DogRegistered(
        originator_id=uuid4(),
        originator_version=1,
        name=name,
    )


def add_trick(dog: Dog, trick: Trick) -> DomainEvent:
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
        tricks=event.state["tricks"],
    )


project_dog = aggregate_projector(mutate_dog)
