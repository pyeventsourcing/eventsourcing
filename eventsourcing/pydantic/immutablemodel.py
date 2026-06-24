from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypeVar

from eventsourcing.domain import (
    TAggregateID,
    datetime_now_with_tzinfo,
    get_metadata_from_context,
)
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Iterable


class Immutable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DomainEvent(Immutable, Generic[TAggregateID]):
    originator_id: TAggregateID
    originator_version: int
    timestamp: datetime = Field(default_factory=datetime_now_with_tzinfo)
    metadata: dict[str, str] = Field(default_factory=get_metadata_from_context)
    event_id: UUID = Field(default_factory=uuid4)


class Aggregate(Immutable, Generic[TAggregateID]):
    id: TAggregateID
    version: int
    created_on: datetime
    modified_on: datetime


class Snapshot(DomainEvent[TAggregateID]):
    topic: str
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: Aggregate[TAggregateID]) -> Snapshot[TAggregateID]:
        return cls(
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
