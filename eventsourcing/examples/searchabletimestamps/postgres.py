from datetime import datetime
from typing import Any, List, Optional, Sequence, Tuple, cast
from uuid import UUID

from eventsourcing.domain import Aggregate
from eventsourcing.examples.searchabletimestamps.persistence import (
    SearchableTimestampsRecorder,
)
from eventsourcing.persistence import ApplicationRecorder, StoredEvent
from eventsourcing.postgres import (
    Factory,
    PostgresApplicationRecorder,
    PostgresConnection,
    PostgresCursor,
    PostgresDatastore,
)


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
            f"INSERT INTO {self.event_timestamps_table_name} VALUES ($1, $2, $3)"
        )
        self.insert_event_timestamp_statement_name = (
            f"insert_{event_timestamps_table_name}".replace(".", "_")
        )
        self.select_event_timestamp_statement = (
            f"SELECT originator_version FROM {self.event_timestamps_table_name} WHERE "
            f"originator_id = $1 AND "
            f"timestamp <= $2 "
            "ORDER BY originator_version DESC "
            "LIMIT 1"
        )

        self.select_event_timestamp_statement_name = (
            f"select_{event_timestamps_table_name}".replace(".", "_")
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

    def _prepare_insert_events(self, conn: PostgresConnection) -> None:
        super()._prepare_insert_events(conn)
        self._prepare(
            conn,
            self.insert_event_timestamp_statement_name,
            self.insert_event_timestamp_statement,
        )

    def _insert_events(
        self,
        c: PostgresCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        notification_ids = super()._insert_events(c, stored_events, **kwargs)

        # Insert event timestamps.
        event_timestamps_data = cast(
            List[Tuple[UUID, datetime, int]], kwargs.get("event_timestamps_data")
        )
        for event_timestamp_data in event_timestamps_data:
            statement_alias = self.statement_name_aliases[
                self.insert_event_timestamp_statement_name
            ]
            c.execute(f"EXECUTE {statement_alias}(%s, %s, %s)", event_timestamp_data)
        return notification_ids

    def get_version_at_timestamp(
        self, originator_id: UUID, timestamp: datetime
    ) -> Optional[int]:
        with self.datastore.get_connection() as conn:
            self._prepare(
                conn,
                self.select_event_timestamp_statement_name,
                self.select_event_timestamp_statement,
            )
            with conn.transaction(commit=False) as curs:
                statement_alias = self.statement_name_aliases[
                    self.select_event_timestamp_statement_name
                ]
                curs.execute(
                    f"EXECUTE {statement_alias}(%s, %s)", [originator_id, timestamp]
                )
                for row in curs.fetchall():
                    return row["originator_version"]
                else:
                    return Aggregate.INITIAL_VERSION - 1


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
