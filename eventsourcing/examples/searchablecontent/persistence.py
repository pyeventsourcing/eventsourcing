from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, List, Tuple

from eventsourcing.persistence import AggregateRecorder

if TYPE_CHECKING:  # pragma: nocover
    from uuid import UUID


class SearchableContentRecorder(AggregateRecorder):
    @abstractmethod
    def search_pages(self, query: str) -> List[UUID]:
        """
        Returns IDs for pages that match query.
        """

    @abstractmethod
    def select_page(self, page_id: UUID) -> Tuple[str, str, str]:
        """
        Returns slug, title and body for given ID.
        """
