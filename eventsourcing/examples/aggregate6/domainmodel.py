from dataclasses import dataclass
from datetime import datetime, timezone
from functools import singledispatch
from time import monotonic
from typing import Iterable, Optional, Tuple, TypeVar, Union
from uuid import UUID, uuid4

from eventsourcing.application import MutatorFunction, ProjectorFunction
from eventsourcing.domain import Snapshot


@dataclass(frozen=True)
class DomainEvent:
    originator_id: UUID
    originator_version: int
    timestamp: datetime


def create_timestamp() -> datetime:
    return datetime.fromtimestamp(monotonic(), timezone.utc)


@dataclass(frozen=True)
class Aggregate:
    id: UUID
    version: int
    created_on: datetime


TAggregate = TypeVar("TAggregate", bound=Aggregate)


def aggregate_projector(
    mutator: MutatorFunction[TAggregate],
) -> ProjectorFunction[TAggregate]:
    def project_aggregate(
        aggregate: Optional[TAggregate], events: Iterable[DomainEvent]
    ) -> Optional[TAggregate]:
        for event in events:
            aggregate = mutator(event, aggregate)
        return aggregate

    return project_aggregate


@dataclass(frozen=True)
class Dog(Aggregate):
    name: str
    tricks: Tuple[str, ...]


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
        timestamp=create_timestamp(),
        name=name,
    )


def add_trick(dog: Dog, trick: str) -> DomainEvent:
    return TrickAdded(
        originator_id=dog.id,
        originator_version=dog.version + 1,
        timestamp=create_timestamp(),
        trick=trick,
    )


@singledispatch
def mutate_dog(
    event: Union[DomainEvent, Snapshot], dog: Optional[Dog]
) -> Optional[Dog]:
    """Mutates aggregate with event."""


@mutate_dog.register
def _(event: DogRegistered, _: None) -> Dog:
    return Dog(
        id=event.originator_id,
        version=event.originator_version,
        created_on=event.timestamp,
        name=event.name,
        tricks=(),
    )


@mutate_dog.register
def _(event: TrickAdded, dog: Dog) -> Dog:
    return Dog(
        id=dog.id,
        version=event.originator_version,
        created_on=event.timestamp,
        name=dog.name,
        tricks=dog.tricks + (event.trick,),
    )


@mutate_dog.register(Snapshot)
def _(event: Snapshot, _: None) -> Dog:
    return Dog(
        id=event.state["id"],
        version=event.state["version"],
        created_on=event.state["created_on"],
        name=event.state["name"],
        tricks=tuple(event.state["tricks"]),  # comes back from JSON as a list
    )


project_dog = aggregate_projector(mutate_dog)
