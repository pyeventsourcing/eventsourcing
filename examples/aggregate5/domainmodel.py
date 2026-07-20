from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from eventsourcing.dataclasses.immutable import DataclassDecision, Immutable
from eventsourcing.domain import AggregateEvent, EventEnvelope
from eventsourcing.errors import ProgrammingError

if TYPE_CHECKING:
    from collections.abc import Iterable


class Dog(Immutable):
    id: str
    version: int
    name: str
    tricks: tuple[str, ...]

    class Registered(DataclassDecision):
        name: str

    class TrickAdded(DataclassDecision):
        trick: str

    def trigger_event(
        self, cls: type[DataclassDecision], **kwargs: Any
    ) -> AggregateEvent[DataclassDecision]:
        return AggregateEvent(
            decision=cls(**kwargs),
            originator_id=self.id,
            originator_version=self.version + 1,
        )

    @staticmethod
    def register(name: str) -> tuple[Dog, AggregateEvent[DataclassDecision]]:
        event = AggregateEvent(
            decision=Dog.Registered(
                name=name,
            ),
            originator_id=str(uuid4()),
            originator_version=1,
        )
        dog = Dog.mutate(event, None)
        return dog, event

    def add_trick(self, trick: str) -> tuple[Dog, AggregateEvent[DataclassDecision]]:
        event = self.trigger_event(Dog.TrickAdded, trick=trick)
        dog = Dog.mutate(event, self)
        return dog, event

    @staticmethod
    def mutate(event: EventEnvelope[DataclassDecision], dog: Dog | None) -> Dog:
        """Mutates aggregate with event."""
        assert isinstance(event, AggregateEvent)
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
        dog: Dog | None, events: Iterable[EventEnvelope[DataclassDecision]]
    ) -> Dog | None:
        for event in events:
            dog = Dog.mutate(event, dog)
        return dog
