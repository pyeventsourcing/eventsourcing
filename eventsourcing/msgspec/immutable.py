from __future__ import annotations

from abc import ABCMeta
from typing import Any, TypeVar, override

import msgspec

import eventsourcing.domain
from eventsourcing.utils import get_topic

_M = TypeVar("_M", bound="ImmutableMeta")


class ImmutableMeta(msgspec.StructMeta, ABCMeta):
    def __new__(
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


class Decision(Immutable, eventsourcing.domain.Decision):
    @override
    def as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__struct_fields__}


class TaggedEvent(eventsourcing.domain.TaggedEvent[Decision]):
    pass


class StreamEvent(eventsourcing.domain.StreamEvent[Decision]):
    pass


class ImmutableAggregate(Immutable):
    id: str
    version: int


class ImmutableAggregateSnapshot(Decision):
    topic: str
    state: bytes

    @classmethod
    def take(cls, aggregate: ImmutableAggregate) -> StreamEvent:
        decision = cls(
            topic=get_topic(type(aggregate)),
            state=msgspec.json.encode(aggregate),
        )
        return StreamEvent(
            decision=decision,
            stream_id=aggregate.id,
            stream_position=aggregate.version,
        )
