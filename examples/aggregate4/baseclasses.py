from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any, cast

from eventsourcing.dataclasses import Decision
from eventsourcing.dataclasses.immutable import (
    coerce_value,
    get_init_types,
)
from eventsourcing.domain import (
    EventEnvelope,
)
from eventsourcing.timestamp import datetime_now_with_tzinfo
from eventsourcing.types import AggregateEventProtocol, WorksWithDecisions
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Self


@dataclass(kw_only=True, frozen=True)
class AggregateEvent(EventEnvelope[Decision]):
    originator_id: str
    originator_version: int


class TimestampedDecision(Decision):
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)


@dataclass(eq=False)
class Aggregate(WorksWithDecisions[Decision]):
    id: str
    version: int
    created_on: datetime
    modified_on: datetime
    _pending_events: list[AggregateEvent] = field(init=False)

    class Snapshot(TimestampedDecision):
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
                topic=get_topic(type(aggregate)),
                state=aggregate_state,
            )

    def trigger_event(
        self,
        event_class: type[Decision],
        **kwargs: Any,
    ) -> None:
        kwargs = kwargs.copy()
        new_event = AggregateEvent(
            decision=event_class(**kwargs),
            originator_id=self.id,
            originator_version=self.version + 1,
        )
        self.apply_event(new_event)
        self.append_event(new_event)

    def append_event(self, *events: AggregateEvent) -> None:
        self._pending_events.extend(events)

    def collect_events(self) -> list[AggregateEvent]:
        events, self._pending_events = self._pending_events, list[AggregateEvent]()
        return events

    def apply_event(self, envelope: AggregateEventProtocol[Decision]) -> None:
        match envelope.decision:
            case Aggregate.Snapshot(state=state):
                validated_state = {}
                init_types = get_init_types(cast(Hashable, type(self)))

                for key, value in state.items():
                    if key in init_types:
                        validated_state[key] = coerce_value(init_types[key], value)
                    else:
                        validated_state[key] = value

                self.__dict__.update(validated_state)
            case _:
                msg = f"For {type(envelope.decision).__qualname__}"
                raise NotImplementedError(msg)

    @classmethod
    def project_events(
        cls,
        _: Self | None,
        events: Iterable[AggregateEventProtocol[Decision]],
    ) -> Self | None:
        aggregate: Self = Aggregate.__new__(cls)
        for event in events:
            aggregate.apply_event(event)
        return aggregate

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        aggregate = super().__new__(cls, *args, **kwargs)
        aggregate._pending_events = []
        return aggregate
