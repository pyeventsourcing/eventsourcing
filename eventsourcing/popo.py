from collections import defaultdict
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set
from uuid import UUID

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    IntegrityError,
    Notification,
    ProcessRecorder,
    StoredEvent,
    Tracking,
)
from eventsourcing.utils import reversed_keys


class POPOAggregateRecorder(AggregateRecorder):
    def __init__(self) -> None:
        self._stored_events: List[StoredEvent] = []
        self._stored_events_index: Dict[UUID, Dict[int, int]] = defaultdict(dict)
        self._database_lock = Lock()

    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        self._insert_events(stored_events, **kwargs)
        return None

    def _insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        with self._database_lock:
            self._assert_uniqueness(stored_events, **kwargs)
            return self._update_table(stored_events, **kwargs)

    def _assert_uniqueness(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> None:
        new = set()
        for s in stored_events:
            # Check events don't already exist.
            if s.originator_version in self._stored_events_index[s.originator_id]:
                raise IntegrityError(f"Stored event already recorded: {s}")
            new.add((s.originator_id, s.originator_version))
        # Check new events are unique.
        if len(new) < len(stored_events):
            raise IntegrityError(f"Stored events are not unique: {stored_events}")

    def _update_table(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        notification_ids = []
        for s in stored_events:
            self._stored_events.append(s)
            self._stored_events_index[s.originator_id][s.originator_version] = (
                len(self._stored_events) - 1
            )
            notification_ids.append(len(self._stored_events))
        return notification_ids

    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:

        with self._database_lock:
            results = []

            index = self._stored_events_index[originator_id]
            positions: Iterable[int]
            if desc:
                positions = reversed_keys(index)
            else:
                positions = index.keys()
            for p in positions:
                if gt is not None:
                    if not p > gt:
                        continue
                if lte is not None:
                    if not p <= lte:
                        continue
                s = self._stored_events[index[p]]
                results.append(s)
                if len(results) == limit:
                    break
            return results


class POPOApplicationRecorder(ApplicationRecorder, POPOAggregateRecorder):
    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        return self._insert_events(stored_events, **kwargs)

    def select_notifications(
        self,
        start: int,
        limit: int,
        stop: Optional[int] = None,
        topics: Sequence[str] = (),
    ) -> List[Notification]:
        with self._database_lock:
            results = []
            i = start - 1
            while True:
                if stop is not None and i > stop - 1:
                    break
                try:
                    s = self._stored_events[i]
                except IndexError:
                    break
                i += 1
                if topics and s.topic not in topics:
                    continue
                n = Notification(
                    id=i,
                    originator_id=s.originator_id,
                    originator_version=s.originator_version,
                    topic=s.topic,
                    state=s.state,
                )
                results.append(n)
                if len(results) == limit:
                    break
            return results

    def max_notification_id(self) -> int:
        with self._database_lock:
            return len(self._stored_events)


class POPOProcessRecorder(ProcessRecorder, POPOApplicationRecorder):
    def __init__(self) -> None:
        super().__init__()
        self._tracking_table: Dict[str, Set[int]] = defaultdict(set)
        self._max_tracking_ids: Dict[str, int] = defaultdict(lambda: 0)

    def _assert_uniqueness(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> None:
        super()._assert_uniqueness(stored_events, **kwargs)
        t: Optional[Tracking] = kwargs.get("tracking", None)
        if t and t.notification_id in self._tracking_table[t.application_name]:
            raise IntegrityError(
                f"Already recorded notification ID {t.notification_id} "
                f"for application {t.application_name}"
            )

    def _update_table(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        notification_ids = super()._update_table(stored_events, **kwargs)
        t: Optional[Tracking] = kwargs.get("tracking", None)
        if t:
            self._tracking_table[t.application_name].add(t.notification_id)
            if self._max_tracking_ids[t.application_name] < t.notification_id:
                self._max_tracking_ids[t.application_name] = t.notification_id
        return notification_ids

    def max_tracking_id(self, application_name: str) -> int:
        with self._database_lock:
            return self._max_tracking_ids[application_name]

    def has_tracking_id(self, application_name: str, notification_id: int) -> bool:
        with self._database_lock:
            return notification_id in self._tracking_table[application_name]


class Factory(InfrastructureFactory):
    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        return POPOAggregateRecorder()

    def application_recorder(self) -> ApplicationRecorder:
        return POPOApplicationRecorder()

    def process_recorder(self) -> ProcessRecorder:
        return POPOProcessRecorder()
