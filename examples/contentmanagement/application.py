from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import (
    AggregateNotFoundError,
    Application,
    EventSourcedLog,
)
from examples.contentmanagement.domainmodel import Page, PageLogged, Slug

if TYPE_CHECKING:
    from collections.abc import Iterator

    from eventsourcing.domain import MutableOrImmutableAggregate
    from eventsourcing.utils import EnvType

PageDetailsType = dict[str, str | Any]


class ContentManagement(Application[UUID]):
    env: ClassVar[dict[str, str]] = {"CONTENTMANAGEMENT_COMPRESSOR_TOPIC": "gzip"}
    snapshotting_intervals: ClassVar[
        dict[type[MutableOrImmutableAggregate[UUID]], int]
    ] = {Page: 5}

    def __init__(self, env: EnvType | None = None) -> None:
        super().__init__(env)
        self.page_log: EventSourcedLog[PageLogged] = EventSourcedLog(
            self.events, uuid5(NAMESPACE_URL, "/page_log"), PageLogged
        )

    def create_page(self, title: str, slug: str) -> int:
        page = Page(title=title, slug=slug, body="")
        page_logged = self.page_log.trigger_event(page_id=page.id)
        index_entry = Slug(slug, page_id=page.id)
        recordings = self.save(page, page_logged, index_entry)
        return recordings[-1].notification.id

    def get_page_by_slug(self, slug: str) -> PageDetailsType:
        page = self._get_page_by_slug(slug)
        return self._details_from_page(page)

    def get_page_by_id(self, page_id: UUID) -> PageDetailsType:
        page = self._get_page_by_id(page_id)
        return self._details_from_page(page)

    def _details_from_page(self, page: Page) -> PageDetailsType:
        return {
            "title": page.title,
            "slug": page.slug,
            "body": page.body,
            "modified_by": page.modified_by,
        }

    def update_title(self, slug: str, title: str) -> int:
        page = self._get_page_by_slug(slug)
        page.update_title(title=title)
        recordings = self.save(page)
        return recordings[-1].notification.id

    def update_slug(self, old_slug: str, new_slug: str) -> int:
        page = self._get_page_by_slug(old_slug)
        page.update_slug(new_slug)
        old_slug_aggregate = self._get_slug(old_slug)
        old_slug_aggregate.update_page(None)
        try:
            new_slug_aggregate = self._get_slug(new_slug)
        except AggregateNotFoundError:
            new_slug_aggregate = Slug(new_slug, page.id)
        else:
            if new_slug_aggregate.page_id is None:
                new_slug_aggregate.update_page(page.id)
            else:
                raise SlugConflictError
        recordings = self.save(page, old_slug_aggregate, new_slug_aggregate)
        return recordings[-1].notification.id

    def update_body(self, slug: str, body: str) -> int:
        page = self._get_page_by_slug(slug)
        page.update_body(body)
        recordings = self.save(page)
        return recordings[-1].notification.id

    def _get_page_by_slug(self, slug: str) -> Page:
        try:
            index = self._get_slug(slug)
        except AggregateNotFoundError:
            raise PageNotFoundError(slug) from None
        if index.page_id is None:
            raise PageNotFoundError(slug)
        page_id = index.page_id
        return self._get_page_by_id(page_id)

    def _get_page_by_id(self, page_id: UUID) -> Page:
        return self.repository.get(page_id)

    def _get_slug(self, slug: str) -> Slug:
        return self.repository.get(Slug.create_id(slug))

    def get_pages(
        self,
        *,
        gt: int | None = None,
        lte: int | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> Iterator[PageDetailsType]:
        for page_logged in self.page_log.get(gt=gt, lte=lte, desc=desc, limit=limit):
            page = self._get_page_by_id(page_logged.page_id)
            yield self._details_from_page(page)


class PageNotFoundError(Exception):
    """Raised when a page is not found."""


class SlugConflictError(Exception):
    """Raised when updating a page to a slug used by another page."""
