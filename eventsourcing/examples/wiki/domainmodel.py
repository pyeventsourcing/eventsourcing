from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.domain import Aggregate, event
from eventsourcing.examples.wiki.utils import diff, patch


USER_ID: ContextVar[Optional[UUID]] = ContextVar('user_id', default=None)


@dataclass
class Page(Aggregate):
    title: str
    body: str = ""

    class Event(Aggregate.Event["Page"]):
        user_id: Optional[UUID] = field(default_factory=USER_ID.get, init=False)

    @event("TitleUpdated")
    def update_title(self, title: str) -> None:
        self.title = title

    def update_body(self, body: str) -> None:
        self._update_body(diff(self.body, body))

    @event("BodyUpdated")
    def _update_body(self, diff: str) -> None:
        self.body = patch(self.body, diff)


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
