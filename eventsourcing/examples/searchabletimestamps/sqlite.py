from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Sequence, Tuple, cast
from uuid import UUID

from eventsourcing.domain import Aggregate
from eventsourcing.examples.searchabletimestamps.persistence import (
    SearchableTimestampsRecorder,
)
from eventsourcing.sqlite import (
    Factory,
    SQLiteApplicationRecorder,
    SQLiteCursor,
    SQLiteDatastore,
)

if TYPE_CHECKING:  # pragma: nocover
    from eventsourcing.persistence import ApplicationRecorder, StoredEvent


class SearchableTimestampsApplicationRecorder(
    SearchableTimestampsRecorder, SQLiteApplicationRecorder
):
    def __init__(
        self,
        datastore: SQLiteDatastore,
        events_table_name: str = "stored_events",
        event_timestamps_table_name: str = "event_timestamps",
    ):
        self.event_timestamps_table_name = event_timestamps_table_name
        super().__init__(datastore, events_table_name)
        self.insert_event_timestamp_statement = (
            f"INSERT INTO {self.event_timestamps_table_name} VALUES (?, ?, ?)"
        )
        self.select_event_timestamp_statement = (
            f"SELECT originator_version FROM {self.event_timestamps_table_name} WHERE "
            "originator_id = ? AND "
            "timestamp <= ? "
            "ORDER BY originator_version DESC "
            "LIMIT 1"
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.event_timestamps_table_name} ("
            "originator_id TEXT, "
            "timestamp timestamp, "
            "originator_version INTEGER, "
            "PRIMARY KEY "
            "(originator_id, timestamp))"
        )
        return statements

    def _insert_events(
        self,
        c: SQLiteCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Sequence[int] | None:
        notification_ids = super()._insert_events(c, stored_events, **kwargs)

        # Insert event timestamps.
        event_timestamps_data = cast(
            List[Tuple[UUID, datetime, int]], kwargs["event_timestamps_data"]
        )
        for originator_id, timestamp, originator_version in event_timestamps_data:
            c.execute(
                self.insert_event_timestamp_statement,
                (originator_id.hex, timestamp, originator_version),
            )

        return notification_ids

    def get_version_at_timestamp(
        self, originator_id: UUID, timestamp: datetime
    ) -> int | None:
        with self.datastore.transaction(commit=False) as c:
            c.execute(
                self.select_event_timestamp_statement, (originator_id.hex, timestamp)
            )
            for row in c.fetchall():
                version = row["originator_version"]
                break
            else:
                version = Aggregate.INITIAL_VERSION - 1
            return version


class SearchableTimestampsInfrastructureFactory(Factory):
    def application_recorder(self) -> ApplicationRecorder:
        recorder = SearchableTimestampsApplicationRecorder(datastore=self.datastore)
        recorder.create_table()
        return recorder


del Factory
