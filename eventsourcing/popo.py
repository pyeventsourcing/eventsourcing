from collections import defaultdict
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    Notification,
    ProcessRecorder,
    RecordConflictError,
    StoredEvent,
    Tracking,
)


class POPOAggregateRecorder(AggregateRecorder):
    def __init__(self) -> None:
        self.stored_events: List[StoredEvent] = []
        self.stored_events_index: Dict[UUID, Dict[int, int]] = defaultdict(dict)
        self.database_lock = Lock()

    def insert_events(self, stored_events: List[StoredEvent], **kwargs: Any) -> None:
        with self.database_lock:
            self.assert_uniqueness(stored_events, **kwargs)
            self.update_table(stored_events, **kwargs)

    def assert_uniqueness(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> None:
        new = set()
        for s in stored_events:
            # Check events don't already exist.
            if s.originator_version in self.stored_events_index[s.originator_id]:
                raise RecordConflictError
            new.add((s.originator_id, s.originator_version))
        # Check new events are unique.
        if len(new) < len(stored_events):
            raise RecordConflictError

    def update_table(self, stored_events: List[StoredEvent], **kwargs: Any) -> None:
        for s in stored_events:
            self.stored_events.append(s)
            self.stored_events_index[s.originator_id][s.originator_version] = (
                len(self.stored_events) - 1
            )

    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:

        with self.database_lock:
            results = []

            index = self.stored_events_index[originator_id]
            positions: Iterable = index.keys()
            if desc:
                positions = reversed(list(positions))
            for p in positions:
                if gt is not None:
                    if not p > gt:
                        continue
                if lte is not None:
                    if not p <= lte:
                        continue
                s = self.stored_events[index[p]]
                results.append(s)
                if len(results) == limit:
                    break
            return results


class POPOApplicationRecorder(ApplicationRecorder, POPOAggregateRecorder):
    def select_notifications(self, start: int, limit: int) -> List[Notification]:
        with self.database_lock:
            results = []
            i = start - 1
            j = i + limit
            for notification_id, s in enumerate(self.stored_events[i:j], start):
                n = Notification(
                    id=notification_id,
                    originator_id=s.originator_id,
                    originator_version=s.originator_version,
                    topic=s.topic,
                    state=s.state,
                )
                results.append(n)
            return results

    def max_notification_id(self) -> int:
        with self.database_lock:
            return len(self.stored_events)


class POPOProcessRecorder(ProcessRecorder, POPOApplicationRecorder):
    def __init__(self) -> None:
        super().__init__()
        self.tracking_table: Dict[str, int] = defaultdict(None)

    def assert_uniqueness(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> None:
        super().assert_uniqueness(stored_events, **kwargs)
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking:
            last = self.tracking_table.get(tracking.application_name, 0)
            if tracking.notification_id <= last:
                raise RecordConflictError

    def update_table(self, stored_events: List[StoredEvent], **kwargs: Any) -> None:
        super().update_table(stored_events, **kwargs)
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking:
            self.tracking_table[tracking.application_name] = tracking.notification_id

    def max_tracking_id(self, application_name: str) -> int:
        with self.database_lock:
            try:
                return self.tracking_table[application_name]
            except KeyError:
                return 0


class Factory(InfrastructureFactory):
    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        return POPOAggregateRecorder()

    def application_recorder(self) -> ApplicationRecorder:
        return POPOApplicationRecorder()

    def process_recorder(self) -> ProcessRecorder:
        return POPOProcessRecorder()
