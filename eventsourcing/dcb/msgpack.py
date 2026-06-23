from __future__ import annotations

from abc import ABCMeta
from typing import Any, TypeVar

import msgspec

from eventsourcing.dcb import api, domain, persistence
from eventsourcing.domain import get_metadata_from_context
from eventsourcing.utils import get_topic, resolve_topic

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
    msgspec.Struct, domain.Decision, metaclass=MsgspecDecisionMeta, kw_only=True
):
    metadata: dict[str, str] = msgspec.field(default_factory=get_metadata_from_context)

    def as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__struct_fields__}


TDecision = TypeVar("TDecision", bound=Decision)


class MessagePackMapper(persistence.DCBMapper):
    def to_dcb_event(self, event: domain.Tagged[Any]) -> api.DCBEvent:
        return api.DCBEvent(
            type=get_topic(type(event.decision)),
            data=msgspec.msgpack.encode(event.decision),
            tags=event.tags,
            uuid=event.uuid,
        )

    def to_domain_event(self, event: api.DCBEvent) -> domain.Tagged[Any]:
        return domain.Tagged(
            tags=event.tags,
            decision=msgspec.msgpack.decode(
                event.data,
                type=resolve_topic(event.type),
            ),
            uuid=event.uuid,
        )
