from __future__ import annotations

from functools import singledispatch
from uuid import uuid4

import msgspec.json

from eventsourcing.domain_new import AggregateEvent, projector
from eventsourcing.errors import ProgrammingError
from eventsourcing.msgspec.immutable import (
    Immutable,
    ImmutableMsgspecAggregate,
    MsgspecDecision,
)


class Trick(Immutable):
    name: str


class Dog(ImmutableMsgspecAggregate):
    name: str
    tricks: tuple[Trick, ...]


class DogRegistered(MsgspecDecision):
    name: str


class TrickAdded(MsgspecDecision):
    trick: Trick


def register_dog(name: str) -> AggregateEvent[MsgspecDecision]:
    return AggregateEvent(
        decision=DogRegistered(name=name),
        originator_id=uuid4(),
        originator_version=1,
    )


def add_trick(dog: Dog, trick: Trick) -> AggregateEvent[MsgspecDecision]:
    return AggregateEvent(
        decision=TrickAdded(trick=trick),
        originator_id=dog.id,
        originator_version=dog.version + 1,
    )


def mutate_dog(
    envelope: AggregateEvent[MsgspecDecision], dog: Dog | None
) -> Dog | None:
    """Mutates aggregate with event."""
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


project_dog = projector(mutate_dog)
