from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from eventsourcing.persistence import Tracking, TrackingRecorder
from eventsourcing.postgres import PostgresTrackingRecorder
from eventsourcing.projection import Projection
from examples.contentmanagement.domainmodel import Page
from examples.contentmanagement.utils import apply_diff
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo
from examples.ftscontentmanagement.postgres import PostgresFtsRecorder

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eventsourcing.domain import AggregateEvent
    from eventsourcing.pydantic.immutable import PydanticDecision


class FtsViewInterface(FtsRecorder, TrackingRecorder, ABC):
    @abstractmethod
    def insert_pages_with_tracking(
        self, pages: Sequence[PageInfo], tracking: Tracking
    ) -> None:
        pass

    @abstractmethod
    def update_pages_with_tracking(
        self, pages: Sequence[PageInfo], tracking: Tracking
    ) -> None:
        pass


class FtsProjection(Projection[FtsViewInterface]):
    def process_event(
        self, envelope: AggregateEvent[PydanticDecision], tracking: Tracking
    ) -> None:
        match envelope.decision:
            case Page.Created(title=title, slug=slug, body=body):
                new_page = PageInfo(
                    id=envelope.originator_id,
                    title=title,
                    slug=slug,
                    body=body,
                )
                self.view.insert_pages_with_tracking([new_page], tracking)
            case Page.BodyUpdated(diff=diff):
                old_page = self.view.select_page(envelope.originator_id)
                new_page = PageInfo(
                    id=envelope.originator_id,
                    slug=old_page.slug,
                    title=old_page.title,
                    body=apply_diff(old_page.body, diff),
                )
                self.view.update_pages_with_tracking([new_page], tracking)
            case _:
                self.view.insert_tracking(tracking)


class PostgresFtsView(PostgresFtsRecorder, PostgresTrackingRecorder, FtsViewInterface):
    def insert_pages_with_tracking(
        self, pages: Sequence[PageInfo], tracking: Tracking
    ) -> None:
        with self.datastore.transaction(commit=True) as curs:
            self._insert_pages(curs, pages)
            self._insert_tracking(curs, tracking)

    def update_pages_with_tracking(
        self, pages: Sequence[PageInfo], tracking: Tracking
    ) -> None:
        with self.datastore.transaction(commit=True) as curs:
            self._update_pages(curs, pages)
            self._insert_tracking(curs, tracking)
