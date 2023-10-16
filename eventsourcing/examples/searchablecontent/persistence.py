from abc import abstractmethod
from typing import List, Tuple
from uuid import UUID

from eventsourcing.persistence import AggregateRecorder


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
