from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.domain import Aggregate, LogEvent, event
from eventsourcing.examples.wiki.utils import apply_patch, create_diff

user_id_cvar: ContextVar[Optional[UUID]] = ContextVar("user_id", default=None)


@dataclass
class Page(Aggregate):
    title: str
    slug: str
    body: str = ""
    modified_by: Optional[UUID] = field(default=None, init=False)

    class Event(Aggregate.Event["Page"]):
        user_id: Optional[UUID] = field(default_factory=user_id_cvar.get, init=False)

        def apply(self, aggregate: "Page") -> None:
            aggregate.modified_by = self.user_id

    @event("SlugUpdated")
    def update_slug(self, slug: str) -> None:
        self.slug = slug

    @event("TitleUpdated")
    def update_title(self, title: str) -> None:
        self.title = title

    def update_body(self, body: str) -> None:
        self._update_body(create_diff(old=self.body, new=body))

    @event("BodyUpdated")
    def _update_body(self, diff: str) -> None:
        self.body = apply_patch(old=self.body, diff=diff)


@dataclass
class Index(Aggregate):
    slug: str
    ref: Optional[UUID]

    class Event(Aggregate.Event["Index"]):
        pass

    @staticmethod
    def create_id(slug: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"/slugs/{slug}")

    @event("RefChanged")
    def update_ref(self, ref: Optional[UUID]) -> None:
        self.ref = ref


class PageLogged(LogEvent):
    page_id: UUID
