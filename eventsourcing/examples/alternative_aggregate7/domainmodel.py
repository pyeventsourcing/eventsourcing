from __future__ import annotations

from datetime import datetime
from functools import reduce, singledispatch
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID, uuid4

from pydantic import BaseModel

from eventsourcing.application import ProjectorFunctionType
from eventsourcing.domain import HasIDVersion
from eventsourcing.utils import get_topic


class DomainEvent(BaseModel):
    class Config:
        allow_mutation = False

    originator_id: UUID
    originator_version: int
    timestamp: datetime


class Aggregate(BaseModel):
    class Config:
        allow_mutation = False

    id: UUID
    version: int
    created_on: datetime


TAggregate = TypeVar("TAggregate", bound=Aggregate)


def aggregate_projector(
    mutator: Callable[[DomainEvent, Optional[TAggregate]], Optional[TAggregate]]
) -> Callable[[Optional[TAggregate], Iterable[DomainEvent]], Optional[TAggregate]]:
    def reducer(
        aggregate: Optional[TAggregate], event: DomainEvent
    ) -> Optional[TAggregate]:
        return mutator(event, aggregate)

    def project_aggregate(
        aggregate: Optional[TAggregate], events: Iterable[DomainEvent]
    ) -> Optional[TAggregate]:
        return reduce(reducer, events, aggregate)

    return project_aggregate


class Dog(Aggregate):
    name: str
    tricks: Tuple[str, ...]


class DogRegistered(DomainEvent):
    name: str


class TrickAdded(DomainEvent):
    trick: str


class Snapshot(DomainEvent):
    topic: str
    state: Dict[str, Any]

    @classmethod
    def take(cls, aggregate: HasIDVersion) -> Snapshot:
        return cls(
            originator_id=aggregate.id,
            originator_version=aggregate.version,
            timestamp=create_timestamp(),
            topic=get_topic(type(aggregate)),
            state=cast(Aggregate, aggregate).dict(),
        )


def register_dog(name: str) -> Tuple[Dog, List[DomainEvent]]:
    event = DogRegistered(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=create_timestamp(),
        name=name,
    )
    return cast(Dog, mutate_dog(event, None)), [event]


def add_trick(dog: Dog, trick: str) -> Tuple[Dog, List[DomainEvent]]:
    event = TrickAdded(
        originator_id=dog.id,
        originator_version=dog.version + 1,
        timestamp=create_timestamp(),
        trick=trick,
    )
    return cast(Dog, mutate_dog(event, dog)), [event]


def create_timestamp() -> datetime:
    return datetime.now()


@singledispatch
def mutate_dog(
    event: Union[DomainEvent, Snapshot], dog: Optional[Dog]
) -> Optional[Dog]:
    """Mutates aggregate with event."""


@mutate_dog.register
def _(event: DogRegistered, _: Dog) -> Dog:
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


@mutate_dog.register
def _(event: Snapshot, _: Dog) -> Dog:
    return Dog(
        id=event.state["id"],
        version=event.state["version"],
        created_on=event.state["created_on"],
        name=event.state["name"],
        tricks=tuple(event.state["tricks"]),  # comes back from JSON as a list
    )


project_dog: ProjectorFunctionType[Dog, DomainEvent] = aggregate_projector(mutate_dog)
