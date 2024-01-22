from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Tuple, cast
from uuid import UUID

from eventsourcing.domain import Aggregate
from eventsourcing.examples.searchabletimestamps.persistence import (
    SearchableTimestampsRecorder,
)
from eventsourcing.postgres import (
    Factory,
    PostgresApplicationRecorder,
    PostgresDatastore,
)

if TYPE_CHECKING:  # pragma: nocover
    from psycopg import Cursor
    from psycopg.rows import DictRow

    from eventsourcing.persistence import ApplicationRecorder, StoredEvent


class SearchableTimestampsApplicationRecorder(
    SearchableTimestampsRecorder, PostgresApplicationRecorder
):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str = "stored_events",
        event_timestamps_table_name: str = "event_timestamps",
    ):
        self.check_table_name_length(event_timestamps_table_name, datastore.schema)
        self.event_timestamps_table_name = event_timestamps_table_name
        super().__init__(datastore, events_table_name)
        self.insert_event_timestamp_statement = (
            f"INSERT INTO {self.event_timestamps_table_name} VALUES (%s, %s, %s)"
        )
        self.select_event_timestamp_statement = (
            f"SELECT originator_version FROM {self.event_timestamps_table_name} WHERE "
            "originator_id = %s AND "
            "timestamp <= %s "
            "ORDER BY originator_version DESC "
            "LIMIT 1"
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.event_timestamps_table_name} ("
            "originator_id uuid NOT NULL, "
            "timestamp timestamp with time zone, "
            "originator_version bigint NOT NULL, "
            "PRIMARY KEY "
            "(originator_id, timestamp))"
        )
        return statements

    def _insert_events(
        self,
        c: Cursor[DictRow],
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        # Insert event timestamps.
        event_timestamps_data = cast(
            List[Tuple[UUID, datetime, int]], kwargs.get("event_timestamps_data")
        )
        for event_timestamp_data in event_timestamps_data:
            c.execute(
                query=self.insert_event_timestamp_statement,
                params=event_timestamp_data,
                prepare=True,
            )
        super()._insert_events(c, stored_events, **kwargs)

    def get_version_at_timestamp(
        self, originator_id: UUID, timestamp: datetime
    ) -> int | None:
        with self.datastore.transaction(commit=False) as curs:
            curs.execute(
                query=self.select_event_timestamp_statement,
                params=(originator_id, timestamp),
                prepare=True,
            )
            for row in curs.fetchall():
                version = row["originator_version"]
                break
            else:
                version = Aggregate.INITIAL_VERSION - 1
            return version


class SearchableTimestampsInfrastructureFactory(Factory):
    def application_recorder(self) -> ApplicationRecorder:
        prefix = (self.datastore.schema + ".") if self.datastore.schema else ""
        prefix += self.env.name.lower() or "stored"
        events_table_name = prefix + "_events"
        event_timestamps_table_name = prefix + "_timestamps"
        recorder = SearchableTimestampsApplicationRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            event_timestamps_table_name=event_timestamps_table_name,
        )
        recorder.create_table()
        return recorder


del Factory
