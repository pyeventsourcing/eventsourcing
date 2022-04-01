from typing import Any, Dict, Iterator, Optional, Union, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import AggregateNotFound, Application, EventSourcedLog
from eventsourcing.examples.wiki.domainmodel import Index, Page, PageLogged
from eventsourcing.utils import EnvType

PageDetailsType = Dict[str, Union[str, Any]]


class WikiApplication(Application):
    env = {"COMPRESSOR_TOPIC": "gzip"}
    snapshotting_intervals = {Page: 5}

    def __init__(self, env: Optional[EnvType] = None) -> None:
        super().__init__(env)
        self.page_log: EventSourcedLog[PageLogged] = EventSourcedLog(
            self.events, uuid5(NAMESPACE_URL, "/page_log"), PageLogged
        )

    def create_page(self, title: str, slug: str) -> None:
        page = Page(title=title, slug=slug)
        page_logged = self.page_log.trigger_event(page_id=page.id)
        index_entry = Index(slug, ref=page.id)
        self.save(page, page_logged, index_entry)

    def get_page_details(self, slug: str) -> PageDetailsType:
        page = self._get_page_by_slug(slug)
        return self._details_from_page(page)

    def _details_from_page(self, page: Page) -> PageDetailsType:
        return {
            "title": page.title,
            "slug": page.slug,
            "body": page.body,
            "modified_by": page.modified_by,
        }

    def update_title(self, slug: str, title: str) -> None:
        page = self._get_page_by_slug(slug)
        page.update_title(title=title)
        self.save(page)

    def update_slug(self, old_slug: str, new_slug: str) -> None:
        page = self._get_page_by_slug(old_slug)
        page.update_slug(new_slug)
        old_index = self._get_index(old_slug)
        old_index.update_ref(None)
        try:
            new_index = self._get_index(new_slug)
        except AggregateNotFound:
            new_index = Index(new_slug, page.id)
        else:
            if new_index.ref is None:
                new_index.update_ref(page.id)
            else:
                raise SlugConflictError()
        self.save(page, old_index, new_index)

    def update_body(self, slug: str, body: str) -> None:
        page = self._get_page_by_slug(slug)
        page.update_body(body)
        self.save(page)

    def _get_page_by_slug(self, slug: str) -> Page:
        try:
            index = self._get_index(slug)
        except AggregateNotFound:
            raise PageNotFound(slug)
        if index.ref is None:
            raise PageNotFound(slug)
        page_id = index.ref
        return self._get_page_by_id(page_id)

    def _get_page_by_id(self, page_id: UUID) -> Page:
        return cast(Page, self.repository.get(page_id))

    def _get_index(self, slug: str) -> Index:
        return cast(Index, self.repository.get(Index.create_id(slug)))

    def get_pages(
        self,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> Iterator[PageDetailsType]:
        for page_logged in self.page_log.get(gt, lte, desc, limit):
            page = self._get_page_by_id(page_logged.page_id)
            yield self._details_from_page(page)


class PageNotFound(Exception):
    """
    Raised when a page is not found.
    """


class SlugConflictError(Exception):
    """
    Raised when updating a page to a slug used by another page.
    """
