from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from eventsourcing.dataclasses import Decision, Immutable
from eventsourcing.domain import StreamEvent
from eventsourcing.errors import ProgrammingError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from eventsourcing.types import StreamEventProtocol


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
    ) -> StreamEvent[Decision]:
        return StreamEvent(
            decision=cls(**kwargs),
            stream_id=self.id,
            stream_position=self.version + 1,
        )

    @staticmethod
    def register(name: str) -> tuple[Dog, StreamEvent[Decision]]:
        event: StreamEvent[Decision] = StreamEvent(
            decision=Dog.Registered(
                name=name,
            ),
            stream_id=str(uuid4()),
            stream_position=1,
        )
        dog = Dog.mutate(event, None)
        return dog, event

    def add_trick(self, trick: str) -> tuple[Dog, StreamEvent[Decision]]:
        event = self.trigger_event(Dog.TrickAdded, trick=trick)
        dog = Dog.mutate(event, self)
        return dog, event

    @staticmethod
    def mutate(event: StreamEventProtocol[Any], dog: Dog | None) -> Dog:
        """Mutates aggregate with event."""
        match event.decision:
            case Dog.Registered(name=name):
                return Dog(
                    id=event.stream_id,
                    version=event.stream_position,
                    name=name,
                    tricks=(),
                )

            case Dog.TrickAdded(trick=trick):
                assert dog is not None
                return Dog(
                    id=dog.id,
                    version=event.stream_position,
                    name=dog.name,
                    tricks=(*dog.tricks, trick),
                )

            case _:
                msg = f"Event type not supported: {type(event)}"
                raise ProgrammingError(msg)

    @staticmethod
    def projector(
        dog: Dog | None, events: Iterable[StreamEventProtocol[Decision]]
    ) -> Dog | None:
        for event in events:
            dog = Dog.mutate(event, dog)
        return dog
