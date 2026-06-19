from __future__ import annotations

from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.domain import Aggregate, DomainEvent, event
from examples.contentmanagement.utils import apply_diff, create_diff


@dataclass
class Page(Aggregate):
    title: str
    """The title of the page."""

    slug: str
    """The slug of the page - used in URLs."""

    body: str
    """The proper content of the page."""

    modified_by: UUID | None = field(init=False)
    """The ID of the user who last modified the page."""

    class Event(Aggregate.Event):
        def apply(self, aggregate: Page) -> None:
            """Sets the aggregate's `modified_by` attribute to the
            value of the event's metadata `user_id` value.
            """
            aggregate.modified_by = self.get_user_id()

        def get_user_id(self) -> UUID:
            return UUID(self.metadata["user_id"])

    @event("SlugUpdated")
    def update_slug(self, slug: str) -> None:
        self.slug = slug

    @event("TitleUpdated")
    def update_title(self, title: str) -> None:
        self.title = title

    def update_body(self, body: str) -> None:
        diff = create_diff(old=self.body, new=body)
        self._update_body(diff=diff)

    class Created(Aggregate.Created, Event):
        title: str
        slug: str
        body: str

    class BodyUpdated(Event):
        diff: str

    @event(BodyUpdated)
    def _update_body(self, diff: str) -> None:
        new_body = apply_diff(old=self.body, diff=diff)
        self.body = new_body


@dataclass
class Slug(Aggregate):
    name: str
    page_id: UUID | None

    class Event(Aggregate.Event):
        pass

    @staticmethod
    def create_id(name: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"/slugs/{name}")

    @event("PageUpdated")
    def update_page(self, page_id: UUID | None) -> None:
        self.page_id = page_id


class PageLogged(DomainEvent):
    page_id: UUID
