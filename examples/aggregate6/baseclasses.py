from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from eventsourcing.dataclasses import Decision
from eventsourcing.metadata import get_metadata_from_context
from eventsourcing.timestamp import datetime_now_with_tzinfo

if TYPE_CHECKING:
    from uuid import UUID


class DomainEvent(Decision):
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)


@dataclass(kw_only=True, frozen=True)
class AggregateEvent:
    decision: DomainEvent
    uuid: UUID = field(default_factory=uuid4)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
    originator_id: str
    originator_version: int


@dataclass(frozen=True)
class Aggregate:
    id: str
    version: int
    created_on: datetime
    modified_on: datetime


class Snapshot(DomainEvent):
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: Aggregate) -> AggregateEvent:
        decision = Snapshot(
            state=aggregate.__dict__,
        )
        return AggregateEvent(
            decision=decision,
            originator_id=aggregate.id,
            originator_version=aggregate.version,
        )
