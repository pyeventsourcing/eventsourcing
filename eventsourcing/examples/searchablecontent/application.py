from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Tuple, cast

from eventsourcing.examples.contentmanagement.application import (
    ContentManagementApplication,
    PageDetailsType,
)
from eventsourcing.examples.contentmanagement.domainmodel import Page
from eventsourcing.examples.searchablecontent.persistence import (
    SearchableContentRecorder,
)

if TYPE_CHECKING:  # pragma: nocover
    from uuid import UUID

    from eventsourcing.domain import DomainEventProtocol, MutableOrImmutableAggregate
    from eventsourcing.persistence import Recording


class SearchableContentApplication(ContentManagementApplication):
    def save(
        self,
        *objs: MutableOrImmutableAggregate | DomainEventProtocol | None,
        **kwargs: Any,
    ) -> List[Recording]:
        insert_pages: List[Tuple[UUID, str, str, str]] = []
        update_pages: List[Tuple[UUID, str, str, str]] = []
        for obj in objs:
            if isinstance(obj, Page):
                if obj.version == len(obj.pending_events):
                    insert_pages.append((obj.id, obj.slug, obj.title, obj.body))
                else:
                    update_pages.append((obj.id, obj.slug, obj.title, obj.body))
        kwargs["insert_pages"] = insert_pages
        kwargs["update_pages"] = update_pages
        return super().save(*objs, **kwargs)

    def search(self, query: str) -> List[PageDetailsType]:
        pages = []
        recorder = cast(SearchableContentRecorder, self.recorder)
        for page_id in recorder.search_pages(query):
            page = self.get_page_by_id(page_id)
            pages.append(page)
        return pages
