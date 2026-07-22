from __future__ import annotations

from abc import ABCMeta
from typing import Any, Self

import msgspec
from typing_extensions import TypeVar

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


class MsgspecImmutable(msgspec.Struct, metaclass=ImmutableMeta):
    pass


class MsgspecDecision(MsgspecImmutable, eventsourcing.domain.AbstractDecision):
    def as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__struct_fields__}


TMsgspecDecision = TypeVar(
    "TMsgspecDecision", bound=MsgspecDecision, default=MsgspecDecision
)


class MsgspecImmutableAggregate(MsgspecImmutable):
    id: str
    version: int


class MsgspecImmutableAggregateSnapshot(MsgspecDecision):
    topic: str
    state: bytes

    @classmethod
    def take(cls, aggregate: MsgspecImmutableAggregate) -> Self:
        return cls(
            topic=get_topic(type(aggregate)),
            state=msgspec.json.encode(aggregate),
        )
