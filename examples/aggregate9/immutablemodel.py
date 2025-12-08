from __future__ import annotations

from collections.abc import Callable
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID  # noqa: TC003

import msgspec

from eventsourcing.domain import datetime_now_with_tzinfo
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Iterable


class Immutable(msgspec.Struct, frozen=True):
    pass


class DomainEvent(Immutable, frozen=True):
    originator_id: UUID
    originator_version: int
    timestamp: datetime


class Aggregate(Immutable, frozen=True):
    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime


class Snapshot(DomainEvent, frozen=True):
    topic: str
    state: bytes

    @classmethod
    def take(cls, aggregate: Aggregate) -> Snapshot:
        return Snapshot(
            originator_id=aggregate.id,
            originator_version=aggregate.version,
            timestamp=datetime_now_with_tzinfo(),
            topic=get_topic(type(aggregate)),
            state=msgspec.json.encode(aggregate),
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
