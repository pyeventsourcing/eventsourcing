from __future__ import annotations

from dataclasses import field
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.domain import event, get_metadata_from_context
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.mutable import PydanticAggregate
from examples.contentmanagement.utils import apply_diff, create_diff


class Page(PydanticAggregate):
    class Event(PydanticDecision):
        def apply(self, aggregate: Page) -> None:
            """Sets the aggregate's `modified_by` attribute to the
            value of the event's metadata `user_id` value.
            """
            aggregate.modified_by = self.get_user_id()

        def get_user_id(self) -> UUID:
            return UUID(get_metadata_from_context()["user_id"])

    class Created(Event):
        title: str
        slug: str
        body: str

    class BodyUpdated(Event):
        diff: str

    @event(Created)
    def __init__(self, title: str, slug: str, body: str):
        self.title = title
        self.slug = slug
        self.body = body
        self.modified_by: UUID | None = field(init=False)

    def update_body(self, body: str) -> None:
        diff = create_diff(old=self.body, new=body)
        self._update_body(diff=diff)

    @event(BodyUpdated)
    def _update_body(self, diff: str) -> None:
        new_body = apply_diff(old=self.body, diff=diff)
        self.body = new_body

    works_with_decision_type = Event

    @event("SlugUpdated")
    def update_slug(self, slug: str) -> None:
        self.slug = slug

    @event("TitleUpdated")
    def update_title(self, title: str) -> None:
        self.title = title


class Slug(PydanticAggregate):
    @event("Created")
    def __init__(self, name: str, page_id: str | None):
        self.name = name
        self.page_id = page_id

    @staticmethod
    def create_id(name: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"/slugs/{name}"))

    @event("PageUpdated")
    def update_page(self, page_id: str | None) -> None:
        self.page_id = page_id


class PageLogged(PydanticDecision):
    page_id: str
