from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from eventsourcing.domain import StreamEvent, projector
from eventsourcing.errors import ProgrammingError
from eventsourcing.msgspec import (
    Decision,
    Immutable,
    ImmutableAggregate,
)

if TYPE_CHECKING:
    from eventsourcing.types import StreamEventProtocol


class Trick(Immutable):
    name: str


class Dog(ImmutableAggregate):
    name: str
    tricks: tuple[Trick, ...]


class DogRegistered(Decision):
    name: str


class TrickAdded(Decision):
    trick: Trick


def register_dog(name: str) -> StreamEvent[Decision]:
    return StreamEvent(
        decision=DogRegistered(name=name),
        stream_id=str(uuid4()),
        stream_position=1,
    )


def add_trick(dog: Dog, trick: Trick) -> StreamEvent[Decision]:
    return StreamEvent(
        decision=TrickAdded(trick=trick),
        stream_id=dog.id,
        stream_position=dog.version + 1,
    )


@projector
def evolve_dog(dog: Dog | None, envelope: StreamEventProtocol[Decision]) -> Dog | None:
    """Mutates aggregate with event."""
    assert isinstance(envelope, StreamEvent)
    match envelope.decision:
        case DogRegistered(name=name):
            return Dog(
                id=envelope.stream_id,
                version=envelope.stream_position,
                name=name,
                tricks=(),
            )
        case TrickAdded(trick=trick):
            assert dog is not None
            return Dog(
                id=dog.id,
                version=envelope.stream_position,
                name=dog.name,
                tricks=(*dog.tricks, trick),
            )
        case _:
            msg = f"Decision type not supported: {envelope.decision}"
            raise ProgrammingError(msg)
