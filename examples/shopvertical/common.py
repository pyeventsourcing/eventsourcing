from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, cast

from eventsourcing.pydantic.application import PydanticApplication
from eventsourcing.pydantic.immutablemodel import Immutable
from examples.shopvertical.events import DomainEvents

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID


class Command(Immutable, ABC):
    @abstractmethod
    def handle(self, events: DomainEvents) -> DomainEvents:
        pass  # pragma: no cover

    @abstractmethod
    def execute(self) -> int | None:
        pass  # pragma: no cover


class Query(Immutable, ABC):
    @abstractmethod
    def execute(self) -> Any:
        pass  # pragma: no cover


class _Globals:
    app = PydanticApplication()


def reset_application() -> None:
    _Globals.app = PydanticApplication()


def get_events(originator_id: UUID) -> DomainEvents:
    return cast(DomainEvents, tuple(_Globals.app.events.get(originator_id)))


def put_events(events: DomainEvents) -> int | None:
    recordings = _Globals.app.events.put(events)
    return recordings[-1].notification.id if recordings else None


def get_all_events(topics: Sequence[str] = ()) -> DomainEvents:
    return cast(
        DomainEvents,
        tuple(
            map(
                _Globals.app.mapper.to_domain_event,
                _Globals.app.recorder.select_notifications(
                    start=None,
                    limit=1000000,
                    topics=topics,
                ),
            )
        ),
    )
