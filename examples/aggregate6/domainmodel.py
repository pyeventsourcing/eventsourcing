from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from eventsourcing.dataclasses import Decision, Immutable
from eventsourcing.domain import AggregateEvent, projector

if TYPE_CHECKING:
    from eventsourcing.types import AggregateEventProtocol


class Dog(Immutable):
    id: str
    version: int
    name: str
    tricks: tuple[str, ...]


class DogRegistered(Decision):
    name: str


class TrickAdded(Decision):
    trick: str


def register_dog(name: str) -> AggregateEvent[Decision]:
    return AggregateEvent(
        decision=DogRegistered(
            name=name,
        ),
        originator_id=str(uuid4()),
        originator_version=1,
    )


def add_trick(dog: Dog, trick: str) -> AggregateEvent[Decision]:
    return AggregateEvent(
        decision=TrickAdded(
            trick=trick,
        ),
        originator_id=dog.id,
        originator_version=dog.version + 1,
    )


@projector
def mutate_dog(dog: Dog | None, event: AggregateEventProtocol[Decision]) -> Dog | None:
    match event.decision:
        case DogRegistered(name=name):
            return Dog(
                id=event.originator_id,
                version=event.originator_version,
                name=name,
                tricks=(),
            )
        case TrickAdded(trick=trick):
            assert dog is not None
            return Dog(
                id=dog.id,
                version=event.originator_version,
                name=dog.name,
                tricks=(*dog.tricks, trick),
            )
        case _:
            msg = f"Type not support: {type(event.decision)}"
            raise TypeError(msg)
