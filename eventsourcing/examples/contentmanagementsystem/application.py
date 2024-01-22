from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Dict, List, cast

from eventsourcing.examples.contentmanagement.domainmodel import Page
from eventsourcing.examples.contentmanagement.utils import apply_patch
from eventsourcing.examples.searchablecontent.persistence import (
    SearchableContentRecorder,
)
from eventsourcing.system import ProcessApplication

if TYPE_CHECKING:  # pragma: nocover
    from uuid import UUID

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.domain import DomainEventProtocol


class SearchIndexApplication(ProcessApplication):
    env: ClassVar[Dict[str, str]] = {
        "COMPRESSOR_TOPIC": "gzip",
    }

    def policy(
        self,
        domain_event: DomainEventProtocol,
        processing_event: ProcessingEvent,
    ) -> None:
        if isinstance(domain_event, Page.Created):
            processing_event.saved_kwargs["insert_pages"] = [(
                domain_event.originator_id,
                domain_event.slug,
                domain_event.title,
                domain_event.body,
            )]
        elif isinstance(domain_event, Page.BodyUpdated):
            recorder = cast(SearchableContentRecorder, self.recorder)
            page_id = domain_event.originator_id
            page_slug, page_title, page_body = recorder.select_page(page_id)
            page_body = apply_patch(page_body, domain_event.diff)
            processing_event.saved_kwargs["update_pages"] = [(
                page_id,
                page_slug,
                page_title,
                page_body,
            )]

    def search(self, query: str) -> List[UUID]:
        recorder = cast(SearchableContentRecorder, self.recorder)
        return recorder.search_pages(query)
