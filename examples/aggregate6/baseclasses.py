from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from typing import Any

from eventsourcing.dataclasses import Decision
from eventsourcing.domain import AggregateEvent
from eventsourcing.timestamp import datetime_now_with_tzinfo


class DomainEvent(Decision):
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)


@dataclass(frozen=True)
class Aggregate:
    id: str
    version: int
    created_on: datetime
    modified_on: datetime


class Snapshot(DomainEvent):
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: Aggregate) -> AggregateEvent[Decision]:
        decision = Snapshot(
            state=aggregate.__dict__,
        )
        return AggregateEvent(
            decision=decision,
            originator_id=aggregate.id,
            originator_version=aggregate.version,
        )
