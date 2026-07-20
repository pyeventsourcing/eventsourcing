from __future__ import annotations

from uuid import uuid4

from eventsourcing.dataclasses.immutable import DataclassDecision, Immutable
from eventsourcing.domain_new import AggregateEvent, EventEnvelope, projector


class Dog(Immutable):
    id: str
    version: int
    name: str
    tricks: tuple[str, ...]


class DogRegistered(DataclassDecision):
    name: str


class TrickAdded(DataclassDecision):
    trick: str


def register_dog(name: str) -> AggregateEvent[DataclassDecision]:
    return AggregateEvent(
        decision=DogRegistered(
            name=name,
        ),
        originator_id=str(uuid4()),
        originator_version=1,
    )


def add_trick(dog: Dog, trick: str) -> AggregateEvent[DataclassDecision]:
    return AggregateEvent(
        decision=TrickAdded(
            trick=trick,
        ),
        originator_id=dog.id,
        originator_version=dog.version + 1,
    )


@projector
def mutate_dog(event: EventEnvelope[DataclassDecision], dog: Dog | None) -> Dog | None:
    assert isinstance(event, AggregateEvent)
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
