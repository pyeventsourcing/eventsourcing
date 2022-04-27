from abc import abstractmethod
from typing import List

from eventsourcing.persistence import ApplicationRecorder


class SearchableContentRecorder(ApplicationRecorder):
    @abstractmethod
    def search_page_bodies(self, query: str) -> List[str]:
        """
        Returns page slugs for page bodies that match query.
        """
