from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import field
from datetime import datetime
from functools import singledispatch
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from eventsourcing.domain import datetime_now_with_tzinfo, get_metadata_from_context
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Iterable


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    originator_id: UUID
    originator_version: int
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)


class Aggregate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime

    def hold_event(self, event: DomainEvent) -> None:
        all_pending_events[id(self)].append(event)

    def collect_events(self) -> list[DomainEvent]:
        try:
            return all_pending_events.pop(id(self))
        except KeyError:  # pragma: no cover
            return []

    def __del__(self) -> None:
        with contextlib.suppress(KeyError):
            all_pending_events.pop(id(self))


class Snapshot(DomainEvent):
    topic: str
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: Aggregate) -> Snapshot:
        return Snapshot(
            originator_id=aggregate.id,
            originator_version=aggregate.version,
            topic=get_topic(type(aggregate)),
            state=aggregate.model_dump(),
        )


TAggregate = TypeVar("TAggregate", bound=Aggregate)
MutatorFunction = Callable[..., TAggregate | None]


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


class Trick(BaseModel):
    name: str


all_pending_events: dict[int, list[DomainEvent]] = defaultdict(list)


class Dog(Aggregate):
    name: str
    tricks: tuple[Trick, ...]


class DogRegistered(DomainEvent):
    name: str


class TrickAdded(DomainEvent):
    trick: Trick


def register_dog(name: str) -> Dog:
    event = DogRegistered(
        originator_id=uuid4(),
        originator_version=1,
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
        trick=Trick(name=trick),
    )
    dog_ = mutate_dog(event, dog)
    assert isinstance(dog_, Dog)
    dog_.hold_event(event)
    return dog_


@singledispatch
def mutate_dog(_: DomainEvent, __: Dog | None) -> Dog | None:
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
        tricks=event.state["tricks"],
    )


project_dog = aggregate_projector(mutate_dog)
