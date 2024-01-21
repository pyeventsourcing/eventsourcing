from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.domain import Aggregate, DomainEvent, event
from eventsourcing.examples.contentmanagement.utils import apply_patch, create_diff

user_id_cvar: ContextVar[UUID | None] = ContextVar("user_id", default=None)


class Page(Aggregate):
    class Event(Aggregate.Event):
        user_id: UUID | None = field(default_factory=user_id_cvar.get, init=False)

        def apply(self, aggregate: Aggregate) -> None:
            cast(Page, aggregate).modified_by = self.user_id

    class Created(Event, Aggregate.Created):
        title: str
        slug: str
        body: str

    def __init__(self, title: str, slug: str, body: str = ""):
        self.title = title
        self.slug = slug
        self.body = body
        self.modified_by: UUID | None = None

    @event("SlugUpdated")
    def update_slug(self, slug: str) -> None:
        self.slug = slug

    @event("TitleUpdated")
    def update_title(self, title: str) -> None:
        self.title = title

    def update_body(self, body: str) -> None:
        self._update_body(create_diff(old=self.body, new=body))

    class BodyUpdated(Event):
        diff: str

    @event(BodyUpdated)
    def _update_body(self, diff: str) -> None:
        self.body = apply_patch(old=self.body, diff=diff)


@dataclass
class Index(Aggregate):
    slug: str
    ref: UUID | None

    class Event(Aggregate.Event):
        pass

    @staticmethod
    def create_id(slug: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"/slugs/{slug}")

    @event("RefChanged")
    def update_ref(self, ref: UUID | None) -> None:
        self.ref = ref


class PageLogged(DomainEvent):
    page_id: UUID
