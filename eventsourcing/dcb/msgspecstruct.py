from __future__ import annotations

from typing import Any, TypeVar

import msgspec

from eventsourcing.dcb.api import DCBEvent
from eventsourcing.dcb.domain import Initialises, Mutates, Tagged
from eventsourcing.dcb.persistence import DCBMapper
from eventsourcing.utils import get_topic, resolve_topic


class Decision(msgspec.Struct, Mutates):
    def _as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__struct_fields__}


TDecision = TypeVar("TDecision", bound=Decision)


class MsgspecStructMapper(DCBMapper[Decision]):
    def to_dcb_event(self, event: Tagged[TDecision]) -> DCBEvent:
        return DCBEvent(
            type=get_topic(type(event.mutates)),
            data=msgspec.msgpack.encode(event.mutates),
            tags=event.tags,
        )

    def to_domain_event(self, event: DCBEvent) -> Tagged[Decision]:
        return Tagged(
            tags=event.tags,
            mutates=msgspec.msgpack.decode(
                event.data,
                type=resolve_topic(event.type),
            ),
        )


class InitialDecision(Decision, Initialises):
    originator_topic: str
