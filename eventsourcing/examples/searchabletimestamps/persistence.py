from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from eventsourcing.persistence import ApplicationRecorder

if TYPE_CHECKING:  # pragma: nocover
    from datetime import datetime
    from uuid import UUID


class SearchableTimestampsRecorder(ApplicationRecorder):
    @abstractmethod
    def get_version_at_timestamp(
        self, originator_id: UUID, timestamp: datetime
    ) -> int | None:
        """
        Returns originator version at timestamp for given originator ID.
        """
