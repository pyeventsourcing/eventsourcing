from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from eventsourcing.domain import AggregateEvent
from examples.aggregate4.baseclasses import Aggregate, TimestampedDecision

if TYPE_CHECKING:
    from eventsourcing.dataclasses import Decision


@dataclass
class Dog(Aggregate):
    name: str
    tricks: list[str]

    class Registered(TimestampedDecision):
        name: str

    class TrickAdded(TimestampedDecision):
        trick: str

    @classmethod
    def register(cls, name: str) -> Dog:
        event = AggregateEvent(
            decision=cls.Registered(
                name=name,
            ),
            originator_id=str(uuid4()),
            originator_version=1,
        )
        dog = cls.project_events(None, [event])
        assert dog is not None
        dog.append_event(event)
        return dog

    def add_trick(self, trick: str) -> None:
        self.trigger_event(self.TrickAdded, trick=trick)

    def apply_event(self, envelope: AggregateEvent[Decision]) -> None:
        match envelope.decision:
            case Dog.Registered(timestamp=timestamp, name=name):
                self.id = envelope.originator_id
                self.version = envelope.originator_version
                self.created_on = timestamp
                self.modified_on = timestamp
                self.name = name
                self.tricks = []
            case Dog.TrickAdded(timestamp=timestamp, trick=trick):
                self.tricks.append(trick)
                self.version = envelope.originator_version
                self.modified_on = timestamp
            case _:
                super().apply_event(envelope)
