from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from eventsourcing.domain import StreamEvent, projector
from examples.aggregate6.baseclasses import DomainEvent

if TYPE_CHECKING:
    from eventsourcing.dataclasses import Decision


@dataclass(kw_only=True, frozen=True)
class Dog:
    id: str
    version: int
    name: str
    tricks: tuple[str, ...]


class DogRegistered(DomainEvent):
    name: str


class TrickAdded(DomainEvent):
    trick: str


def register_dog(name: str) -> StreamEvent[Decision]:
    return StreamEvent(
        decision=DogRegistered(name=name),
        stream_id=str(uuid4()),
        stream_position=1,
    )


def add_trick(dog: Dog, trick: str) -> StreamEvent[Decision]:
    return StreamEvent(
        decision=TrickAdded(trick=trick),
        stream_id=dog.id,
        stream_position=dog.version + 1,
    )


@projector
def mutate_dog(dog: Dog | None, event: StreamEvent[Decision]) -> Dog | None:
    match event.decision:
        case DogRegistered(name=name):
            return Dog(
                id=event.stream_id,
                version=event.stream_position,
                name=name,
                tricks=(),
            )
        case TrickAdded(trick=trick):
            assert dog is not None
            return Dog(
                id=dog.id,
                version=event.stream_position,
                name=dog.name,
                tricks=(*dog.tricks, trick),
            )
        case _:
            msg = f"Type not support: {type(event.decision)}"
            raise TypeError(msg)
