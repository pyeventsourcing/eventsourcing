from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypeVar

from eventsourcing.dispatch import singledispatchmethod

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Self
    from uuid import UUID


@dataclass(frozen=True)
class DomainEvent:
    originator_id: UUID
    originator_version: int
    timestamp: datetime

    @staticmethod
    def create_timestamp() -> datetime:
        return datetime.now(tz=UTC)


TAggregate = TypeVar("TAggregate", bound="Aggregate")


@dataclass(frozen=True)
class Aggregate:
    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime

    def trigger_event(
        self,
        event_class: type[DomainEvent],
        **kwargs: Any,
    ) -> DomainEvent:
        kwargs = kwargs.copy()
        kwargs.update(
            originator_id=self.id,
            originator_version=self.version + 1,
            timestamp=event_class.create_timestamp(),
        )
        return event_class(**kwargs)

    @classmethod
    def projector(
        cls,
        aggregate: Self | None,
        events: Iterable[DomainEvent],
    ) -> Self | None:
        for event in events:
            aggregate = cls.mutate(event, aggregate)
        return aggregate

    @singledispatchmethod[Any]
    @staticmethod
    def mutate(event: DomainEvent, aggregate: TAggregate | None) -> TAggregate | None:
        """Mutates aggregate with event."""

    @dataclass(frozen=True)
    class Snapshot(DomainEvent):
        state: dict[str, Any]

        @classmethod
        def take(cls, aggregate: Aggregate) -> Aggregate.Snapshot:
            return Aggregate.Snapshot(
                originator_id=aggregate.id,
                originator_version=aggregate.version,
                timestamp=DomainEvent.create_timestamp(),
                state=aggregate.__dict__,
            )
