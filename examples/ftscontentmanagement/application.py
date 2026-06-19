from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from examples.contentmanagement.application import ContentManagement, PageDetailsType
from examples.contentmanagement.domainmodel import Page
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo

if TYPE_CHECKING:
    from eventsourcing.domain import DomainEventProtocol, MutableOrImmutableAggregate
    from eventsourcing.persistence import Recording


class FtsContentManagement(ContentManagement):
    def save(
        self,
        *objs: MutableOrImmutableAggregate | DomainEventProtocol | None,
        **kwargs: Any,
    ) -> list[Recording]:
        insert_pages: list[PageInfo] = []
        update_pages: list[PageInfo] = []
        for obj in objs:
            if isinstance(obj, Page):
                if obj.version == len(obj.pending_events):
                    insert_pages.append(PageInfo(obj.id, obj.slug, obj.title, obj.body))
                else:
                    update_pages.append(PageInfo(obj.id, obj.slug, obj.title, obj.body))
        kwargs["insert_pages"] = insert_pages
        kwargs["update_pages"] = update_pages
        return super().save(*objs, **kwargs)

    def search(self, query: str) -> list[PageDetailsType]:
        pages = []
        recorder = cast("FtsRecorder", self.recorder)
        for page_id in recorder.search_pages(query):
            page = self.get_page_by_id(page_id)
            pages.append(page)
        return pages
