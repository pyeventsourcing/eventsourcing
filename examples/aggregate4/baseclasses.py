from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any, TypeVar, cast

from eventsourcing.dataclasses.immutable import (
    DataclassDecision,
    coerce_value,
    get_init_types,
)
from eventsourcing.domain_new import (
    AggregateEvent,
    EventEnvelope,
    WorksWithDecisions,
    datetime_now_with_tzinfo,
)
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Self

TAggregate = TypeVar("TAggregate", bound="Aggregate")


class TimestampedDataclassDecision(DataclassDecision):
    timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)


@dataclass(eq=False)
class Aggregate(WorksWithDecisions[DataclassDecision]):
    id: str
    version: int
    created_on: datetime
    modified_on: datetime
    _pending_events: list[AggregateEvent[DataclassDecision]] = field(init=False)

    class Snapshot(TimestampedDataclassDecision):
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
        event_class: type[DataclassDecision],
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

    def append_event(self, *events: AggregateEvent[DataclassDecision]) -> None:
        self._pending_events.extend(events)

    def collect_events(self) -> list[AggregateEvent[DataclassDecision]]:
        events, self._pending_events = self._pending_events, []
        return events

    def apply_event(self, event: EventEnvelope[DataclassDecision]) -> None:
        match event.decision:
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
                msg = f"For {type(event.decision).__qualname__}"
                raise NotImplementedError(msg)

    @classmethod
    def project_events(
        cls,
        _: Self | None,
        events: Iterable[EventEnvelope[DataclassDecision]],
    ) -> Self | None:
        aggregate: Self = Aggregate.__new__(cls)
        for event in events:
            aggregate.apply_event(event)
        return aggregate

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        aggregate = super().__new__(cls, *args, **kwargs)
        aggregate._pending_events = []
        return aggregate
