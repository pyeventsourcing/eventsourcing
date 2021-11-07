from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional, Union
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.domain import Aggregate, AggregateEvent, event
from eventsourcing.examples.wiki.utils import apply_patch, create_diff

user_id_cvar: ContextVar[Optional[UUID]] = ContextVar("user_id", default=None)


__event__: Union["Page.Event", Any] = None


@dataclass
class Page(Aggregate):
    title: str
    slug: str
    body: str = ""
    modified_by: Optional[UUID] = field(default=None, init=False)

    class Event(Aggregate.Event["Page"]):
        user_id: Optional[UUID] = field(default_factory=user_id_cvar.get, init=False)

    @event("SlugUpdated", inject_event=True)
    def update_slug(self, slug: str) -> None:
        self.slug = slug
        self.modified_by = __event__.user_id

    @event("TitleUpdated", inject_event=True)
    def update_title(self, title: str) -> None:
        self.title = title
        self.modified_by = globals()["__event__"].user_id

    def update_body(self, body: str) -> None:
        self._update_body(create_diff(old=self.body, new=body))

    @event("BodyUpdated")
    def _update_body(self, diff: str, user_id: Optional[UUID] = None) -> None:
        self.body = apply_patch(old=self.body, diff=diff)
        self.modified_by = user_id


@dataclass
class Index(Aggregate):
    slug: str
    ref: Optional[UUID]

    @staticmethod
    def create_id(slug: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"/slugs/{slug}")

    @event("RefChanged")
    def update_ref(self, ref: Optional[UUID]) -> None:
        self.ref = ref


class PageLogged(AggregateEvent[Aggregate]):
    page_id: UUID
