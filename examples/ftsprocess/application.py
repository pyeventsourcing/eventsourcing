from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from eventsourcing.persistence import Recorder
from eventsourcing.pydantic import AggregatesApplication, Decision
from eventsourcing.system import ProcessApplication
from examples.contentmanagement.domainmodel import Page
from examples.contentmanagement.utils import apply_diff
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo

if TYPE_CHECKING:
    from eventsourcing.application import ProcessingEvent
    from eventsourcing.domain import AggregateEvent


class FtsProcess(AggregatesApplication, ProcessApplication[Decision]):
    env: ClassVar[dict[str, str]] = {
        "COMPRESSOR_TOPIC": "gzip",
    }

    def policy(
        self,
        envelope: AggregateEvent[Decision],
        processing_event: ProcessingEvent[Decision],
    ) -> None:
        match envelope.decision:
            case Page.Created(title=title, slug=slug, body=body):
                processing_event.collect_events(
                    insert_pages=[
                        PageInfo(
                            id=envelope.originator_id,
                            title=title,
                            slug=slug,
                            body=body,
                        )
                    ]
                )
            case Page.BodyUpdated(diff=diff):
                recorder = cast(FtsRecorder, cast(Recorder, self.recorder))
                page = recorder.select_page(envelope.originator_id)
                page_body = apply_diff(page.body, diff)
                processing_event.collect_events(
                    update_pages=[
                        PageInfo(
                            id=envelope.originator_id,
                            slug=page.slug,
                            title=page.title,
                            body=page_body,
                        )
                    ]
                )

    def search(self, query: str) -> list[str]:
        recorder = cast(FtsRecorder, cast(Recorder, self.recorder))
        return recorder.search_pages(query)
