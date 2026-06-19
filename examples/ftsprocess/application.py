from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.system import ProcessApplication
from examples.contentmanagement.domainmodel import Page
from examples.contentmanagement.utils import apply_diff
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.domain import DomainEventProtocol


class FtsProcess(ProcessApplication):
    env: ClassVar[dict[str, str]] = {
        "COMPRESSOR_TOPIC": "gzip",
    }

    @singledispatchmethod
    def policy(
        self,
        domain_event: DomainEventProtocol,
        processing_event: ProcessingEvent,
    ) -> None:
        if isinstance(domain_event, Page.Created):
            processing_event.collect_events(
                insert_pages=[
                    PageInfo(
                        id=domain_event.originator_id,
                        slug=domain_event.slug,
                        title=domain_event.title,
                        body=domain_event.body,
                    )
                ]
            )
        elif isinstance(domain_event, Page.BodyUpdated):
            recorder = cast("FtsRecorder", self.recorder)
            page_id = domain_event.originator_id
            page = recorder.select_page(page_id)
            page_body = apply_diff(page.body, domain_event.diff)
            processing_event.collect_events(
                update_pages=[
                    PageInfo(
                        id=page_id,
                        slug=page.slug,
                        title=page.title,
                        body=page_body,
                    )
                ]
            )

    def search(self, query: str) -> list[UUID]:
        recorder = cast("FtsRecorder", self.recorder)
        return recorder.search_pages(query)
