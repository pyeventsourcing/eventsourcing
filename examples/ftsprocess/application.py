from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from eventsourcing.domain import AggregateEvent, EventEnvelope
from eventsourcing.persistence import Recorder
from eventsourcing.pydantic.application import PydanticApplication
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.system import ProcessApplication
from examples.contentmanagement.domainmodel import Page
from examples.contentmanagement.utils import apply_diff
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo

if TYPE_CHECKING:
    from eventsourcing.application import ProcessingEvent


class FtsProcess(PydanticApplication, ProcessApplication[PydanticDecision]):
    env: ClassVar[dict[str, str]] = {
        "COMPRESSOR_TOPIC": "gzip",
    }

    def policy(
        self,
        envelope: EventEnvelope[PydanticDecision],
        processing_event: ProcessingEvent[PydanticDecision],
    ) -> None:
        match envelope:
            case AggregateEvent(
                decision=Page.Created(title=title, slug=slug, body=body),
                originator_id=page_id,
            ):
                processing_event.collect_events(
                    insert_pages=[
                        PageInfo(
                            id=page_id,
                            title=title,
                            slug=slug,
                            body=body,
                        )
                    ]
                )
            case AggregateEvent(
                decision=Page.BodyUpdated(diff=diff),
                originator_id=page_id,
            ):

                recorder = cast(FtsRecorder, cast(Recorder, self.recorder))
                page = recorder.select_page(page_id)
                page_body = apply_diff(page.body, diff)
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

    def search(self, query: str) -> list[str]:
        recorder = cast(FtsRecorder, cast(Recorder, self.recorder))
        return recorder.search_pages(query)
