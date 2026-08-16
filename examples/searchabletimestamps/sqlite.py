from __future__ import annotations

import datetime
import sqlite3
from typing import TYPE_CHECKING, Any, cast, override

from eventsourcing.sqlite import (
    SQLiteApplicationRecorder,
    SQLiteCursor,
    SQLiteDatastore,
    SQLiteFactory,
)
from examples.searchabletimestamps.persistence import SearchableTimestampsRecorder

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from eventsourcing.persistence import ApplicationRecorder, StoredEvent


def adapt_date_iso(val: datetime.date) -> str:
    """Adapt datetime.date to ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_iso(val: datetime.datetime) -> str:
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_epoch(val: datetime.datetime) -> int:
    """Adapt datetime.datetime to Unix timestamp."""
    return int(val.timestamp())


sqlite3.register_adapter(datetime.date, adapt_date_iso)
sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
# sqlite3.register_adapter(datetime.datetime, adapt_datetime_epoch)


def convert_date(val: bytes) -> datetime.date:
    """Convert ISO 8601 date to datetime.date object."""
    return datetime.date.fromisoformat(val.decode())


def convert_datetime(val: bytes) -> datetime.datetime:
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.datetime.fromisoformat(val.decode())


def convert_timestamp(val: bytes) -> datetime.datetime:
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return datetime.datetime.fromtimestamp(int(val), datetime.UTC)


sqlite3.register_converter("date", convert_date)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("timestamp", convert_timestamp)


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

    @override
    def construct_create_table_statements(self) -> list[str]:
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

    @override
    def _insert_events(
        self,
        c: SQLiteCursor,
        stored_events: Sequence[StoredEvent],
        **kwargs: Any,
    ) -> Sequence[int] | None:
        notification_ids = super()._insert_events(c, stored_events, **kwargs)

        # Insert event timestamps.
        event_timestamps_data = cast(
            "list[tuple[UUID, datetime.datetime, int]]", kwargs["event_timestamps_data"]
        )
        for originator_id, timestamp, originator_version in event_timestamps_data:
            c.execute(
                self.insert_event_timestamp_statement,
                (originator_id, timestamp, originator_version),
            )

        return notification_ids

    @override
    def get_version_at_timestamp(
        self, originator_id: str, timestamp: datetime.datetime
    ) -> int | None:
        with self.datastore.transaction(commit=False) as c:
            c.execute(self.select_event_timestamp_statement, (originator_id, timestamp))
            for row in c.fetchall():
                return row["originator_version"]
            return None


class SearchableTimestampsInfrastructureFactory(SQLiteFactory):
    @override
    def application_recorder(self) -> ApplicationRecorder:
        recorder = SearchableTimestampsApplicationRecorder(datastore=self.datastore)
        recorder.create_table()
        return recorder


del SQLiteFactory
