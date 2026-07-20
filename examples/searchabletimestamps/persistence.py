from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from eventsourcing.persistence import ApplicationRecorder

if TYPE_CHECKING:
    from datetime import datetime


class SearchableTimestampsRecorder(ApplicationRecorder):
    @abstractmethod
    def get_version_at_timestamp(
        self, originator_id: str, timestamp: datetime
    ) -> int | None:
        """Returns originator version at timestamp for given originator ID."""
