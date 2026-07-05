from __future__ import annotations

from abc import ABCMeta
from typing import Any, TypeVar

import msgspec

import eventsourcing.dcb.domain
from eventsourcing.dcb.persistence import DCBMapper

_M = TypeVar("_M", bound="MsgspecDecisionMeta")


class MsgspecDecisionMeta(ABCMeta, msgspec.StructMeta):
    def __new__(
        mcls: type[_M],
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        **kwargs: Any,
    ) -> _M:
        return super(ABCMeta, mcls).__new__(mcls, name, bases, namespace, **kwargs)


class Decision(
    msgspec.Struct,
    eventsourcing.dcb.domain.Decision,
    metaclass=MsgspecDecisionMeta,
    kw_only=True,
):
    def as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__struct_fields__}


class MsgspecMapper(DCBMapper[Decision]):
    def _to_data(self, decision: Decision) -> bytes:
        return msgspec.msgpack.encode(decision)

    def _to_decision(self, data: bytes, decision_class: type[Decision]) -> Decision:
        return msgspec.msgpack.decode(data, type=decision_class)
