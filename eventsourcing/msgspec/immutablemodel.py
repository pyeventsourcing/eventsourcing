from __future__ import annotations

from collections.abc import Callable
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID, uuid4

import msgspec
from msgspec import field

from eventsourcing.domain import (
    datetime_now_with_tzinfo,
    get_metadata_from_context,
)
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Iterable


_M = TypeVar("_M", bound="ImmutableMeta")


class ImmutableMeta(msgspec.StructMeta):
    def __new__(  # noqa: PYI019
        mcls: type[_M],
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        **kwargs: Any,
    ) -> _M:
        kwargs.setdefault("frozen", True)
        return super().__new__(mcls, name, bases, namespace, **kwargs)


class Immutable(msgspec.Struct, metaclass=ImmutableMeta):
    pass


class DomainEvent(Immutable, frozen=True, kw_only=True):
    originator_id: UUID
    originator_version: int
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
    event_id: UUID = field(default_factory=uuid4)


class Aggregate(Immutable, frozen=True):
    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime


class Snapshot(DomainEvent):
    topic: str
    state: bytes

    @classmethod
    def take(cls, aggregate: Aggregate) -> Snapshot:
        return cls(
            originator_id=aggregate.id,
            originator_version=aggregate.version,
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
