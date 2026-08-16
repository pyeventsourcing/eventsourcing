from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from eventsourcing.dataclasses import Decision, Immutable
from eventsourcing.domain import AggregateEvent
from eventsourcing.errors import ProgrammingError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from eventsourcing.types import AggregateEventProtocol


class Dog(Immutable):
    id: str
    version: int
    name: str
    tricks: tuple[str, ...]

    class Registered(Decision):
        name: str

    class TrickAdded(Decision):
        trick: str

    def trigger_event(
        self, cls: type[Decision], **kwargs: Any
    ) -> AggregateEvent[Decision]:
        return AggregateEvent(
            decision=cls(**kwargs),
            originator_id=self.id,
            originator_version=self.version + 1,
        )

    @staticmethod
    def register(name: str) -> tuple[Dog, AggregateEvent[Decision]]:
        event: AggregateEvent[Decision] = AggregateEvent(
            decision=Dog.Registered(
                name=name,
            ),
            originator_id=str(uuid4()),
            originator_version=1,
        )
        dog = Dog.mutate(event, None)
        return dog, event

    def add_trick(self, trick: str) -> tuple[Dog, AggregateEvent[Decision]]:
        event = self.trigger_event(Dog.TrickAdded, trick=trick)
        dog = Dog.mutate(event, self)
        return dog, event

    @staticmethod
    def mutate(event: AggregateEventProtocol[Any], dog: Dog | None) -> Dog:
        """Mutates aggregate with event."""
        match event.decision:
            case Dog.Registered(name=name):
                return Dog(
                    id=event.originator_id,
                    version=event.originator_version,
                    name=name,
                    tricks=(),
                )

            case Dog.TrickAdded(trick=trick):
                assert dog is not None
                return Dog(
                    id=dog.id,
                    version=event.originator_version,
                    name=dog.name,
                    tricks=(*dog.tricks, trick),
                )

            case _:
                msg = f"Event type not supported: {type(event)}"
                raise ProgrammingError(msg)

    @staticmethod
    def projector(
        dog: Dog | None, events: Iterable[AggregateEventProtocol[Decision]]
    ) -> Dog | None:
        for event in events:
            dog = Dog.mutate(event, dog)
        return dog
