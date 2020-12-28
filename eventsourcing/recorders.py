from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from eventsourcing.notification import Notification
from eventsourcing.storedevent import StoredEvent


class OperationalError(Exception):
    pass


class RecordConflictError(Exception):
    pass


class Recorder(ABC):
    pass


class AggregateRecorder(Recorder):
    @abstractmethod
    def insert_events(
        self,
        stored_events: List[StoredEvent],
        **kwargs,
    ) -> None:
        """
        Writes stored events into database.
        """

    @abstractmethod
    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        """
        Reads stored events from database.
        """


class ApplicationRecorder(AggregateRecorder):
    @abstractmethod
    def select_notifications(
        self, start: int, limit: int
    ) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """

    @abstractmethod
    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """


class ProcessRecorder(ApplicationRecorder):
    @abstractmethod
    def max_tracking_id(
        self, application_name: str
    ) -> int:
        pass
