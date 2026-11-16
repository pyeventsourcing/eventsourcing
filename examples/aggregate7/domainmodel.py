from __future__ import annotations

from datetime import datetime  # noqa:TC003
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import Field

from eventsourcing.domain import (
    StreamEvent,
    projector,
)
from eventsourcing.errors import ProgrammingError
from eventsourcing.pydantic import (
    Decision,
    Immutable,
    ImmutableAggregate,
)
from eventsourcing.timestamp import datetime_now_with_tzinfo

if TYPE_CHECKING:
    from eventsourcing.types import StreamEventProtocol


class Trick(Immutable):
    name: str


class TimestampedAggregate(ImmutableAggregate):
    created_on: datetime
    modified_on: datetime


class Dog(TimestampedAggregate):
    name: str
    tricks: tuple[Trick, ...]


class TimestampedDecision(Decision):
    timestamp: datetime = Field(default_factory=datetime_now_with_tzinfo)


class DogRegistered(TimestampedDecision):
    name: str


class TrickAdded(TimestampedDecision):
    trick: Trick


def register_dog(name: str) -> StreamEvent[Decision]:
    return StreamEvent(
        decision=DogRegistered(
            name=name,
        ),
        stream_id=str(uuid4()),
        stream_position=1,
    )


def add_trick(dog: Dog, trick: Trick) -> StreamEvent[Decision]:
    return StreamEvent(
        decision=TrickAdded(
            trick=trick,
        ),
        stream_id=dog.id,
        stream_position=dog.version + 1,
    )


@projector
def evolve_dog(dog: Dog | None, envelope: StreamEventProtocol[Decision]) -> Dog | None:
    """Mutates aggregate with event."""
    match envelope.decision:
        case DogRegistered(name=name, timestamp=timestamp):
            return Dog(
                id=envelope.stream_id,
                version=envelope.stream_position,
                created_on=timestamp,
                modified_on=timestamp,
                name=name,
                tricks=(),
            )

        case TrickAdded(trick=trick, timestamp=timestamp):
            assert dog is not None
            return Dog(
                id=dog.id,
                version=envelope.stream_position,
                created_on=dog.created_on,
                modified_on=timestamp,
                name=dog.name,
                tricks=(*dog.tricks, trick),
            )
        case _:
            raise ProgrammingError
