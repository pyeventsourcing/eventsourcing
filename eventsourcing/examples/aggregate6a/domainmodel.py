from __future__ import annotations

import contextlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import singledispatch
from typing import Callable, Dict, Iterable, List, Optional, Tuple, TypeVar
from uuid import UUID, uuid4

from eventsourcing.domain import Snapshot


@dataclass(frozen=True)
class DomainEvent:
    originator_id: UUID
    originator_version: int
    timestamp: datetime


def create_timestamp() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True)
class Aggregate:
    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime

    def hold_event(self, event: DomainEvent) -> None:
        all_pending_events[id(self)].append(event)

    def collect_events(self) -> List[DomainEvent]:
        try:
            return all_pending_events.pop(id(self))
        except KeyError:  # pragma: no cover
            return []

    def __del__(self) -> None:
        with contextlib.suppress(KeyError):
            all_pending_events.pop(id(self))


TAggregate = TypeVar("TAggregate", bound=Aggregate)
MutatorFunction = Callable[..., Optional[TAggregate]]


def aggregate_projector(
    mutator: MutatorFunction[TAggregate],
) -> Callable[[TAggregate | None, Iterable[DomainEvent]], TAggregate | None]:
    def project_aggregate(
        aggregate: TAggregate | None, events: Iterable[DomainEvent]
    ) -> TAggregate | None:
        for event in events:
            aggregate = mutator(event, aggregate)
        return aggregate

    return project_aggregate


all_pending_events: Dict[int, List[DomainEvent]] = defaultdict(list)


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


def register_dog(name: str) -> Dog:
    event = DogRegistered(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=create_timestamp(),
        name=name,
    )
    dog = mutate_dog(event, None)
    assert isinstance(dog, Dog)
    dog.hold_event(event)
    return dog


def add_trick(dog: Dog, trick: str) -> Dog:
    event = TrickAdded(
        originator_id=dog.id,
        originator_version=dog.version + 1,
        timestamp=create_timestamp(),
        trick=trick,
    )
    dog_ = mutate_dog(event, dog)
    assert isinstance(dog_, Dog)
    dog_.hold_event(event)
    return dog_


@singledispatch
def mutate_dog(_: DomainEvent | Snapshot, __: Dog | None) -> Dog | None:
    """Mutates aggregate with event."""


@mutate_dog.register
def _(event: DogRegistered, _: None) -> Dog:
    return Dog(
        id=event.originator_id,
        version=event.originator_version,
        created_on=event.timestamp,
        modified_on=event.timestamp,
        name=event.name,
        tricks=(),
    )


@mutate_dog.register
def _(event: TrickAdded, dog: Dog) -> Dog:
    return Dog(
        id=dog.id,
        version=event.originator_version,
        created_on=dog.created_on,
        modified_on=event.timestamp,
        name=dog.name,
        tricks=(*dog.tricks, event.trick),
    )


@mutate_dog.register
def _(event: Snapshot, _: None) -> Dog:
    return Dog(
        id=event.state["id"],
        version=event.state["version"],
        created_on=event.state["created_on"],
        modified_on=event.state["modified_on"],
        name=event.state["name"],
        tricks=tuple(event.state["tricks"]),  # comes back from JSON as a list
    )


project_dog = aggregate_projector(mutate_dog)
