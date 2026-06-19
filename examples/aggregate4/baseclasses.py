from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import uuid4

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import datetime_now_with_tzinfo, get_metadata_from_context
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime
    from typing import Self
    from uuid import UUID

TAggregate = TypeVar("TAggregate", bound="Aggregate")


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    originator_version: int
    originator_id: UUID
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
    event_id: UUID = field(default_factory=uuid4)


@dataclass
class Aggregate:
    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime
    _pending_events: list[DomainEvent]

    @dataclass(frozen=True)
    class Snapshot(DomainEvent):
        topic: str
        state: dict[str, Any]

        @classmethod
        def take(
            cls,
            aggregate: Aggregate,
        ) -> Aggregate.Snapshot:
            aggregate_state = dict(aggregate.__dict__)
            aggregate_state.pop("_pending_events")
            return Aggregate.Snapshot(
                originator_id=aggregate.id,
                originator_version=aggregate.version,
                topic=get_topic(type(aggregate)),
                state=aggregate_state,
            )

    def trigger_event(
        self,
        event_class: type[DomainEvent],
        **kwargs: Any,
    ) -> None:
        kwargs = kwargs.copy()
        kwargs.update(
            originator_id=self.id,
            originator_version=self.version + 1,
        )
        new_event = event_class(**kwargs)
        self.apply_event(new_event)
        self.append_event(new_event)

    def append_event(self, *events: DomainEvent) -> None:
        self._pending_events.extend(events)

    def collect_events(self) -> list[DomainEvent]:
        events, self._pending_events = self._pending_events, []
        return events

    @singledispatchmethod
    def apply_event(self, event: DomainEvent) -> None:
        msg = f"For {type(event).__qualname__}"
        raise NotImplementedError(msg)

    @apply_event.register(Snapshot)
    def _(self, event: Snapshot) -> None:
        self.__dict__.update(event.state)

    @classmethod
    def project_events(
        cls,
        _: Self | None,
        events: Iterable[DomainEvent],
    ) -> Self:
        aggregate: Self = Aggregate.__new__(cls)
        for event in events:
            aggregate.apply_event(event)
        return aggregate

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        aggregate = super().__new__(cls, *args, **kwargs)
        aggregate._pending_events = []
        return aggregate
