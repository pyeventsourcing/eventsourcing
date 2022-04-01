from dataclasses import dataclass
from datetime import datetime
from functools import singledispatch
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID, uuid4

from eventsourcing.application import ProjectorFunctionType
from eventsourcing.domain import HasIDVersion, HasOriginatorIDVersion, Snapshot


@dataclass(frozen=True)
class DomainEvent(HasOriginatorIDVersion):
    originator_id: UUID
    originator_version: int
    timestamp: datetime

    @classmethod
    def create_timestamp(cls) -> datetime:
        return datetime.now()


TAggregate = TypeVar("TAggregate", bound="Aggregate")


@dataclass(frozen=True)
class Aggregate(HasIDVersion):
    id: UUID
    version: int
    created_on: datetime


def trigger_event(
    aggregate: TAggregate,
    event_class: Type[DomainEvent],
    **kwargs: Any,
) -> DomainEvent:
    # Impose the required common domain event attribute values.
    kwargs = kwargs.copy()
    kwargs.update(
        originator_id=aggregate.id,
        originator_version=aggregate.version + 1,
        timestamp=event_class.create_timestamp(),
    )
    return event_class(**kwargs)


def aggregate_projector(
    mutator: Callable[[DomainEvent, Optional[TAggregate]], Optional[TAggregate]]
) -> Callable[[Optional[TAggregate], Iterable[DomainEvent]], Optional[TAggregate]]:
    def project_aggregate(
        aggregate: Optional[TAggregate], events: Iterable[DomainEvent]
    ) -> Optional[TAggregate]:
        for event in events:
            aggregate = mutator(event, aggregate)
        return aggregate

    return project_aggregate


@dataclass(frozen=True)
class DogRegistered(DomainEvent):
    name: str


@dataclass(frozen=True)
class TrickAdded(DomainEvent):
    trick: str


@dataclass(frozen=True)
class Dog(Aggregate):
    name: str
    tricks: List[str]


def register_dog(name: str) -> Tuple[Dog, List[DomainEvent]]:
    event = DogRegistered(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=DomainEvent.create_timestamp(),
        name=name,
    )
    dog = mutate_dog(event, None)
    assert dog is not None
    return dog, [event]


def add_trick(dog: Dog, trick: str) -> Tuple[Dog, List[DomainEvent]]:
    event = trigger_event(aggregate=dog, event_class=TrickAdded, trick=trick)
    return cast(Dog, mutate_dog(event, dog)), [event]


@singledispatch
def mutate_dog(
    event: Union[DomainEvent, Snapshot[Dog]], dog: Optional[Dog]
) -> Optional[Dog]:
    """Mutates aggregate with event."""


@mutate_dog.register(DogRegistered)
def _(event: DogRegistered, _: Dog) -> Dog:
    return Dog(
        id=event.originator_id,
        version=event.originator_version,
        created_on=event.timestamp,
        name=event.name,
        tricks=[],
    )


@mutate_dog.register(TrickAdded)
def _(event: TrickAdded, dog: Dog) -> Dog:
    return Dog(
        id=dog.id,
        version=event.originator_version,
        created_on=event.timestamp,
        name=dog.name,
        tricks=dog.tricks + [event.trick],
    )


@mutate_dog.register(Snapshot)
def _(event: Snapshot[Dog], dog: Dog) -> Dog:
    return Dog(
        id=event.state["id"],
        version=event.state["version"],
        created_on=event.state["created_on"],
        name=event.state["name"],
        tricks=event.state["tricks"],
    )


project_dog: ProjectorFunctionType[Dog, DomainEvent] = aggregate_projector(mutate_dog)
