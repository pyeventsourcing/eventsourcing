from typing import (
    Any,
    Dict,
    Generic,
    Iterator,
    Mapping,
    Optional,
    Type,
    Union,
    cast,
)
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.domain import Aggregate, AggregateEvent, TDomainEvent
from eventsourcing.examples.wiki.domainmodel import Index, Page, PageLogged
from eventsourcing.persistence import EventStore

PageDetailsType = Dict[str, Union[str, Any]]


class WikiApplication(Application[Aggregate]):
    env = {"COMPRESSOR_TOPIC": "gzip"}
    snapshotting_intervals = {Page: 5}

    def __init__(self, env: Optional[Mapping[str, str]] = None) -> None:
        super().__init__(env)
        self.page_log: Log[PageLogged] = Log(
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

    def get_pages(self, limit: int = 10, offset: int = 0) -> Iterator[PageDetailsType]:
        for page_logged in self.page_log.get(limit, offset):
            page = self._get_page_by_id(page_logged.page_id)
            yield self._details_from_page(page)


class Log(Generic[TDomainEvent]):
    def __init__(
        self,
        events: EventStore[AggregateEvent[Aggregate]],
        originator_id: UUID,
        logged_cls: Type[TDomainEvent],
    ):
        self.events = events
        self.originator_id = originator_id
        self.logged_cls = logged_cls

    def trigger_event(self, **kwargs: Any) -> TDomainEvent:
        last_logged = self._get_last_logged()
        if last_logged:
            next_originator_version = last_logged.originator_version + 1
        else:
            next_originator_version = Aggregate.INITIAL_VERSION
        return self.logged_cls(  # type: ignore
            originator_id=self.originator_id,
            originator_version=next_originator_version,
            timestamp=self.logged_cls.create_timestamp(),
            **kwargs,
        )

    def get(self, limit: int = 10, offset: int = 0) -> Iterator[TDomainEvent]:
        # Calculate lte.
        lte = None
        if offset > 0:
            last = self._get_last_logged()
            if last:
                lte = last.originator_version - offset

        # Get logged events.
        return cast(
            Iterator[TDomainEvent],
            self.events.get(
                originator_id=self.originator_id,
                lte=lte,
                desc=True,
                limit=limit,
            ),
        )

    def _get_last_logged(
        self,
    ) -> Optional[TDomainEvent]:
        events = self.events.get(originator_id=self.originator_id, desc=True, limit=1)
        try:
            return cast(TDomainEvent, next(events))
        except StopIteration:
            return None


class PageNotFound(Exception):
    """
    Raised when a page is not found.
    """


class SlugConflictError(Exception):
    """
    Raised when updating a page to a slug used by another page.
    """
