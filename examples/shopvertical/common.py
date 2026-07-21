from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeAlias

from eventsourcing.pydantic.application import PydanticAggregatesApplication
from eventsourcing.pydantic.immutable import Immutable, PydanticDecision

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eventsourcing.domain import AggregateEvent

    Events: TypeAlias = Sequence[AggregateEvent[PydanticDecision]]


class Command(Immutable, ABC):
    @abstractmethod
    def handle(self, events: Events) -> Events:
        pass  # pragma: no cover

    @abstractmethod
    def execute(self) -> int | None:
        pass  # pragma: no cover


class Query(Immutable, ABC):
    @abstractmethod
    def execute(self) -> Any:
        pass  # pragma: no cover


class _Globals:
    app = PydanticAggregatesApplication()


def reset_application() -> None:
    _Globals.app = PydanticAggregatesApplication()


def get_events(originator_id: str) -> Events:
    return tuple(_Globals.app.events.get(originator_id))


def put_events(events: Events) -> int | None:
    recordings = _Globals.app.events.put(events)
    return recordings[-1].notification.id if recordings else None


def get_all_events(topics: Sequence[str] = ()) -> Events:
    return tuple(
        map(
            _Globals.app.mapper.to_domain_event,
            _Globals.app.recorder.select_notifications(
                start=None,
                limit=1000000,
                topics=topics,
            ),
        )
    )
