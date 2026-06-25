from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import uuid4

from eventsourcing.domain import (
    MutatorFunction,
    ProjectorFunction,
    TDomainEvent,
    datetime_now_with_tzinfo,
    get_metadata_from_context,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime
    from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    originator_id: UUID
    originator_version: int
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class Aggregate:
    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime


@dataclass(frozen=True)
class Snapshot(DomainEvent):
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: Aggregate) -> Snapshot:
        return Snapshot(
            originator_id=aggregate.id,
            originator_version=aggregate.version,
            state=aggregate.__dict__,
        )


TAggregate = TypeVar("TAggregate", bound=Aggregate)


def aggregate_projector(
    mutator: MutatorFunction[TDomainEvent, TAggregate],
) -> ProjectorFunction[TAggregate, TDomainEvent]:
    def project_aggregate(
        aggregate: TAggregate | None, events: Iterable[TDomainEvent]
    ) -> TAggregate | None:
        for event in events:
            aggregate = mutator(event, aggregate)
        return aggregate

    return project_aggregate
