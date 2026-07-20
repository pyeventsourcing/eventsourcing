from __future__ import annotations

from datetime import datetime  # noqa:TC003
from uuid import uuid4

from pydantic import Field

from eventsourcing.domain_new import (
    AggregateEvent,
    EventEnvelope,
    datetime_now_with_tzinfo,
    projector,
)
from eventsourcing.errors import ProgrammingError
from eventsourcing.pydantic.immutable import (
    Immutable,
    ImmutablePydanticAggregate,
    PydanticDecision,
)


class Trick(Immutable):
    name: str


class TimestampedAggregate(ImmutablePydanticAggregate):
    created_on: datetime
    modified_on: datetime


class Dog(TimestampedAggregate):
    name: str
    tricks: tuple[Trick, ...]


class TimestampedDecision(PydanticDecision):
    timestamp: datetime = Field(default_factory=datetime_now_with_tzinfo)


class DogRegistered(TimestampedDecision):
    name: str


class TrickAdded(TimestampedDecision):
    trick: Trick


def register_dog(name: str) -> AggregateEvent[PydanticDecision]:
    return AggregateEvent(
        decision=DogRegistered(
            name=name,
        ),
        originator_id=str(uuid4()),
        originator_version=1,
    )


def add_trick(dog: Dog, trick: Trick) -> AggregateEvent[PydanticDecision]:
    return AggregateEvent(
        decision=TrickAdded(
            trick=trick,
        ),
        originator_id=dog.id,
        originator_version=dog.version + 1,
    )


@projector
def evolve_dog(
    envelope: EventEnvelope[PydanticDecision], dog: Dog | None
) -> Dog | None:
    """Mutates aggregate with event."""
    assert isinstance(envelope, AggregateEvent)
    match envelope.decision:
        case DogRegistered(name=name, timestamp=timestamp):
            return Dog(
                id=envelope.originator_id,
                version=envelope.originator_version,
                created_on=timestamp,
                modified_on=timestamp,
                name=name,
                tricks=(),
            )

        case TrickAdded(trick=trick, timestamp=timestamp):
            assert dog is not None
            return Dog(
                id=dog.id,
                version=envelope.originator_version,
                created_on=dog.created_on,
                modified_on=timestamp,
                name=dog.name,
                tricks=(*dog.tricks, trick),
            )
        case _:
            raise ProgrammingError
