from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Dict, Iterable, List, Optional, Type, TypeVar
from uuid import UUID, uuid4

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import HasIDVersionFields, HasOriginatorIDVersion, Snapshot


@dataclass(frozen=True)
class DomainEvent(HasOriginatorIDVersion):
    originator_version: int
    originator_id: UUID
    timestamp: datetime

    @staticmethod
    def create_timestamp() -> datetime:
        return datetime.fromtimestamp(monotonic(), timezone.utc)


TAggregate = TypeVar("TAggregate", bound="Aggregate")


class Aggregate(HasIDVersionFields, ABC):
    id: UUID
    version: int
    created_on: datetime

    def __init__(self, event: DomainEvent):
        self.id = event.originator_id
        self.version = event.originator_version
        self.created_on = event.timestamp

    def trigger_event(
        self,
        event_class: Type[DomainEvent],
        **kwargs: Any,
    ) -> None:
        kwargs = kwargs.copy()
        kwargs.update(
            originator_id=self.id,
            originator_version=self.version + 1,
            timestamp=event_class.create_timestamp(),
        )
        new_event = event_class(**kwargs)
        self.apply(new_event)
        self._pending_events.append(new_event)

    @abstractmethod
    def apply(self: TAggregate, event: DomainEvent) -> None:
        """Applies event to aggregate."""

    def collect_events(self) -> List[DomainEvent]:
        events, self._pending_events = self._pending_events, []
        return events

    @classmethod
    def projector(
        cls: Type[TAggregate],
        aggregate: Optional[TAggregate],
        events: Iterable[DomainEvent],
    ) -> Optional[TAggregate]:
        aggregate = object.__new__(cls)
        for event in events:
            aggregate.apply(event)
        return aggregate

    __pending_events: Dict[int, List[DomainEvent]] = defaultdict(list)

    @property
    def _pending_events(self) -> List[DomainEvent]:
        return type(self).__pending_events[id(self)]

    @_pending_events.setter
    def _pending_events(self, pending_events: List[DomainEvent]) -> None:
        type(self).__pending_events[id(self)] = pending_events

    def __del__(self) -> None:
        try:
            type(self).__pending_events.pop(id(self))
        except KeyError:
            pass


class Dog(Aggregate):
    @dataclass(frozen=True)
    class Registered(DomainEvent):
        name: str

    def __init__(self, name: str) -> None:
        event = self.Registered(
            originator_id=uuid4(),
            originator_version=1,
            timestamp=DomainEvent.create_timestamp(),
            name=name,
        )
        self.apply(event)
        self._pending_events.append(event)

    @singledispatchmethod
    def apply(self, event: DomainEvent) -> None:
        """Applies event to aggregate."""

    @apply.register(Registered)
    def _(self, event: Registered) -> None:
        super().__init__(event)
        self.name = event.name
        self.tricks: List[str] = []

    @dataclass(frozen=True)
    class TrickAdded(DomainEvent):
        trick: str

    def add_trick(self, trick: str) -> None:
        self.trigger_event(self.TrickAdded, trick=trick)

    @apply.register(TrickAdded)
    def _(self, event: TrickAdded) -> None:
        self.tricks.append(event.trick)
        self.version = event.originator_version

    @apply.register(Snapshot)
    def _(self, event: Snapshot[TAggregate]) -> None:
        self.__dict__.update(event.state)
