from abc import abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from eventsourcing.persistence import ApplicationRecorder


class SearchableRecorder(ApplicationRecorder):
    @abstractmethod
    def get_version_at_timestamp(
        self, originator_id: UUID, timestamp: datetime
    ) -> Optional[int]:
        """
        Returns originator version at timestamp for given originator ID.
        """
