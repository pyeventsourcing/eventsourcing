from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from eventsourcing.domain import AggregateEvent, projector
from eventsourcing.errors import ProgrammingError
from eventsourcing.msgspec import (
    Decision,
    Immutable,
    ImmutableAggregate,
)

if TYPE_CHECKING:
    from eventsourcing.types import AggregateEventProtocol


class Trick(Immutable):
    name: str


class Dog(ImmutableAggregate):
    name: str
    tricks: tuple[Trick, ...]


class DogRegistered(Decision):
    name: str


class TrickAdded(Decision):
    trick: Trick


def register_dog(name: str) -> AggregateEvent[Decision]:
    return AggregateEvent(
        decision=DogRegistered(name=name),
        originator_id=str(uuid4()),
        originator_version=1,
    )


def add_trick(dog: Dog, trick: Trick) -> AggregateEvent[Decision]:
    return AggregateEvent(
        decision=TrickAdded(trick=trick),
        originator_id=dog.id,
        originator_version=dog.version + 1,
    )


@projector
def evolve_dog(
    dog: Dog | None, envelope: AggregateEventProtocol[Decision]
) -> Dog | None:
    """Mutates aggregate with event."""
    assert isinstance(envelope, AggregateEvent)
    match envelope.decision:
        case DogRegistered(name=name):
            return Dog(
                id=envelope.originator_id,
                version=envelope.originator_version,
                name=name,
                tricks=(),
            )
        case TrickAdded(trick=trick):
            assert dog is not None
            return Dog(
                id=dog.id,
                version=envelope.originator_version,
                name=dog.name,
                tricks=(*dog.tricks, trick),
            )
        case _:
            msg = f"Decision type not supported: {envelope.decision}"
            raise ProgrammingError(msg)
