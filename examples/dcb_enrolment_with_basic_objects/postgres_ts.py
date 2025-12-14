from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypedDict

from psycopg.sql import SQL, Identifier

from eventsourcing.dcb.api import (
    DCBAppendCondition,
    DCBEvent,
    DCBQuery,
    DCBQueryItem,
    DCBReadResponse,
    DCBRecorder,
    DCBSequencedEvent,
    DCBSubscription,
)
from eventsourcing.dcb.persistence import (
    DCBInfrastructureFactory,
)
from eventsourcing.dcb.popo import SimpleDCBReadResponse
from eventsourcing.persistence import IntegrityError, ProgrammingError
from eventsourcing.postgres import (
    BasePostgresFactory,
    PostgresDatastore,
    PostgresRecorder,
    PostgresTrackingRecorder,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from typing_extensions import Self


PG_TYPE_NAME_DCB_EVENT_TS = "dcb_event"

PG_TYPE_DCB_EVENT = SQL("""
CREATE TYPE {schema}.{type_name} AS (
    type text,
    data bytea,
    tags text[],
    text_vector tsvector
)
""")

PG_TABLE_DCB_EVENTS = SQL("""
CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
    sequence_position bigserial PRIMARY KEY,
    type text NOT NULL ,
    data bytea,
    tags text[] NOT NULL,
    text_vector tsvector
) WITH (
  autovacuum_enabled = true,
  autovacuum_vacuum_threshold = 100000000,  -- Effectively disables VACUUM
  autovacuum_vacuum_scale_factor = 0.5,     -- Same here, high scale factor
  autovacuum_analyze_threshold = 1000,      -- Triggers ANALYZE more often
  autovacuum_analyze_scale_factor = 0.01    -- Triggers after 1% new rows
)
""")

PG_TABLE_INDEX_DCB_EVENT_TEXT_VECTOR = SQL("""
CREATE INDEX IF NOT EXISTS {index_name}
ON {schema}.{table} USING GIN (text_vector)
""")

PG_FUNCTION_NAME_DCB_SELECT_EVENTS_TS = "dcb_select_events"

SQL_STATEMENT_DCB_SELECT_EVENTS = SQL("""
SELECT * FROM {select_events}((%s), (%s), (%s))
""")

PG_FUNCTION_DCB_SELECT_EVENTS = SQL("""
CREATE OR REPLACE FUNCTION {select_events}(
    text_query tsquery,
    after bigint,
    max_results bigint DEFAULT NULL
)
RETURNS TABLE (
    sequence_position bigint,
    type text,
    data bytea,
    tags text[]
)
LANGUAGE plpgsql
STABLE
PARALLEL SAFE
AS
$BODY$
DECLARE
    max_pos bigint;
BEGIN
    -- Get the maximum sequence position
    SELECT MAX(t.sequence_position)
    FROM {schema}.{table} t
    INTO max_pos;

    -- Return the max position as the first row
    RETURN QUERY SELECT max_pos, NULL::text, NULL::bytea, NULL::text[];

    IF text_query <> '' THEN
       -- There's a text query...
        IF after is NULL THEN
            -- For initial command query - no 'after'
            RETURN QUERY
            SELECT t.sequence_position, t.type, t.data, t.tags
            FROM {schema}.{table} t
            WHERE t.text_vector @@ text_query
            ORDER BY t.sequence_position ASC
            LIMIT max_results;
        ELSE
            -- More unusual to get here - 'text_query' and 'after'
            RETURN QUERY
            SELECT t.sequence_position, t.type, t.data, t.tags
            FROM {schema}.{table} t
            WHERE t.text_vector @@ text_query
            AND t.sequence_position > COALESCE(after, 0)
            ORDER BY t.sequence_position ASC
            LIMIT max_results;
        END IF;
    ELSE
        -- For propagating the state of an application...
        RETURN QUERY
        SELECT t.sequence_position, t.type, t.data, t.tags
        FROM {schema}.{table} t
        WHERE t.sequence_position > COALESCE(after, 0)
        ORDER BY t.sequence_position ASC
        LIMIT max_results;
    END IF;
END;
$BODY$;
""")

PG_FUNCTION_NAME_DCB_CHECK_APPEND_CONDITION_TS = "dcb_check_append_condition"

PG_FUNCTION_DCB_CHECK_APPEND_CONDITION = SQL("""
CREATE OR REPLACE FUNCTION {check_append_condition}(
    text_query tsquery,
    after bigint
)
RETURNS boolean
LANGUAGE plpgsql
STABLE
PARALLEL SAFE
AS
$BODY$
DECLARE
    append_condition_failed boolean;
BEGIN
    after = COALESCE(after, 0);
    IF (text_query = '') THEN
        SELECT EXISTS (
            SELECT 1
            FROM {schema}.{table}
            WHERE sequence_position > after
            LIMIT 1
        )
        INTO append_condition_failed;
    ELSIF (after = 0) THEN
        SELECT EXISTS (
            SELECT 1
            FROM {schema}.{table}
            WHERE text_vector @@ text_query
            LIMIT 1
        )
        INTO append_condition_failed;
    ELSE
        SELECT EXISTS (
            SELECT 1
            FROM {schema}.{table}
            WHERE sequence_position > after
            AND text_vector @@ text_query
            LIMIT 1
        )
        INTO append_condition_failed;
    END IF;
    RETURN append_condition_failed;
END;
$BODY$;
""")

PG_FUNCTION_NAME_DCB_INSERT_EVENTS_TS = "dcb_insert_events"

PG_FUNCTION_DCB_INSERT_EVENTS = SQL("""
CREATE OR REPLACE FUNCTION {insert_events}(
    events {schema}.{event_type}[]
)
RETURNS TABLE (
    sequence_position bigint
)
LANGUAGE plpgsql
AS
$BODY$
BEGIN
    RETURN QUERY
    INSERT INTO {schema}.{table} AS t (type, data, tags, text_vector)
    SELECT type, data, tags, text_vector FROM unnest(events)
    RETURNING t.sequence_position;
END;
$BODY$
""")

PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS = "dcb_append_events"

SQL_STATEMENT_CALL_DCB_APPEND_EVENTS = SQL("""
CALL {append_events}((%s), (%s), (%s))
""")

PG_PROCEDURE_DCB_APPEND_EVENTS = SQL("""
CREATE OR REPLACE PROCEDURE {append_events} (
    in events {schema}.{event_type}[],
    in text_query tsquery,
    inout after bigint
)
LANGUAGE plpgsql
AS
$BODY$
DECLARE
    append_condition_failed boolean;
BEGIN
    after = COALESCE(after, 0);
    IF (after < 0) THEN
        append_condition_failed = FALSE;
    ELSE
        SELECT {check_append_condition}(
            text_query, after
        ) INTO append_condition_failed;
    END IF;
    IF NOT append_condition_failed THEN
        SELECT MAX(sequence_position)
        FROM {insert_events}(events)
        INTO after;
        NOTIFY {channel};
    ELSE
        after = -1;
    END IF;
    RETURN;
END;
$BODY$
""")


class PostgresDCBRecorderTS(DCBRecorder, PostgresRecorder):
    def __init__(
        self,
        datastore: PostgresDatastore,
        *,
        events_table_name: str = "dcb_events",
    ):
        super().__init__(datastore)
        self.check_identifier_length(events_table_name)
        self.events_table_name = events_table_name
        self.pg_index_name_text_vector = self.events_table_name + "_text_vector_idx"
        self.check_identifier_length(self.pg_index_name_text_vector)
        self.pg_channel_name = events_table_name.replace(".", "_")
        self.datastore.db_type_names.add(PG_TYPE_NAME_DCB_EVENT_TS)
        self.datastore.register_type_adapters()

        self.sql_statement_select_events = SQL_STATEMENT_DCB_SELECT_EVENTS.format(
            select_events=Identifier(PG_FUNCTION_NAME_DCB_SELECT_EVENTS_TS)
        )
        self.sql_call_append_events = SQL_STATEMENT_CALL_DCB_APPEND_EVENTS.format(
            append_events=Identifier(PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS),
        )
        self.sql_create_statements.extend(
            [
                PG_TABLE_DCB_EVENTS.format(
                    schema=Identifier(self.datastore.schema),
                    table_name=Identifier(self.events_table_name),
                ),
                PG_TABLE_INDEX_DCB_EVENT_TEXT_VECTOR.format(
                    index_name=Identifier(self.pg_index_name_text_vector),
                    schema=Identifier(self.datastore.schema),
                    table=Identifier(self.events_table_name),
                ),
                PG_TYPE_DCB_EVENT.format(
                    schema=Identifier(self.datastore.schema),
                    type_name=Identifier(PG_TYPE_NAME_DCB_EVENT_TS),
                ),
                PG_FUNCTION_DCB_INSERT_EVENTS.format(
                    insert_events=Identifier(PG_FUNCTION_NAME_DCB_INSERT_EVENTS_TS),
                    schema=Identifier(self.datastore.schema),
                    event_type=Identifier(PG_TYPE_NAME_DCB_EVENT_TS),
                    table=Identifier(self.events_table_name),
                ),
                PG_FUNCTION_DCB_SELECT_EVENTS.format(
                    select_events=Identifier(PG_FUNCTION_NAME_DCB_SELECT_EVENTS_TS),
                    schema=Identifier(self.datastore.schema),
                    table=Identifier(self.events_table_name),
                ),
                PG_FUNCTION_DCB_CHECK_APPEND_CONDITION.format(
                    check_append_condition=Identifier(
                        PG_FUNCTION_NAME_DCB_CHECK_APPEND_CONDITION_TS
                    ),
                    schema=Identifier(self.datastore.schema),
                    table=Identifier(self.events_table_name),
                ),
                PG_PROCEDURE_DCB_APPEND_EVENTS.format(
                    append_events=Identifier(PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS),
                    schema=Identifier(self.datastore.schema),
                    event_type=Identifier(PG_TYPE_NAME_DCB_EVENT_TS),
                    check_append_condition=Identifier(
                        PG_FUNCTION_NAME_DCB_CHECK_APPEND_CONDITION_TS
                    ),
                    table=Identifier(self.events_table_name),
                    insert_events=Identifier(PG_FUNCTION_NAME_DCB_INSERT_EVENTS_TS),
                    channel=Identifier(self.pg_channel_name),
                ),
            ]
        )

    def read(
        self,
        query: DCBQuery | None = None,
        *,
        after: int | None = None,
        limit: int | None = None,
    ) -> DCBReadResponse:
        # Prepare arguments and invoke pg function.
        if not query or not query.items:
            text_query = ""
        else:
            text_query = self.construct_text_query(query.items)

        with self.datastore.get_connection() as conn:
            result = conn.execute(
                self.sql_statement_select_events,
                (text_query, after, limit),
            ).fetchall()

            max_position = result[0]["sequence_position"]
            events = [
                DCBSequencedEvent(
                    event=DCBEvent(
                        type=row["type"],
                        data=row["data"],
                        tags=row["tags"],
                    ),
                    position=row["sequence_position"],
                )
                for row in result[1:]
            ]
            if limit is None:
                head = max_position
            else:
                head = events[-1].position if events else None

            return SimpleDCBReadResponse(iter(events), head)

    def subscribe(
        self,
        query: DCBQuery | None = None,
        *,
        after: int | None = None,
    ) -> DCBSubscription[Self]:
        raise NotImplementedError  # pragma: no cover

    def append(
        self, events: Sequence[DCBEvent], condition: DCBAppendCondition | None = None
    ) -> int:
        if len(events) == 0:
            msg = "Should be at least one event. Avoid this elsewhere"
            raise ProgrammingError(msg)

        # Prepare 'events' argument.
        pg_dcb_events = [
            self.construct_pg_dcb_event(
                type=event.type,
                data=event.data,
                tags=event.tags,
            )
            for event in events
        ]

        # Prepare 'text_query' and 'after' arguments.
        text_query = ""
        if condition:
            if condition.fail_if_events_match.items:
                text_query = self.construct_text_query(
                    condition.fail_if_events_match.items,
                )
            after = condition.after
        else:
            after = -1  # Indicates no "fail condition".

        # Invoke pg procedure.
        with self.datastore.get_connection() as conn, conn.cursor() as curs:
            result = curs.execute(
                self.sql_call_append_events,
                [pg_dcb_events, text_query, after],
            ).fetchone()
            assert result is not None
            max_position = result["after"]
            assert isinstance(max_position, int)

            if max_position == -1:  # Indicates "fail condition" failed.
                raise IntegrityError
            return max_position

    def construct_text_query(self, query_items: list[DCBQueryItem]) -> str:
        text_queries = [
            self.construct_text_query_from_query_item(query_item)
            for query_item in query_items
        ]
        return " | ".join([f"({t})" for t in text_queries])

    def construct_text_query_from_query_item(self, query_item: DCBQueryItem) -> str:
        types = self.prefix_types(self.replace_reserved_chars(query_item.types))
        tags = self.prefix_tags(self.replace_reserved_chars(query_item.tags))
        types_tq = " | ".join(types)
        tags_tq = " & ".join(tags)
        return f"({types_tq}) & {tags_tq}" if types and tags else types_tq or tags_tq

    def construct_text_vector(self, type: str, tags: list[str]) -> str:  # noqa: A002
        self.assert_no_reserved_prefixes([type, *tags])
        type = self.prefix_types(self.replace_reserved_chars([type]))[0]  # noqa: A001
        tags = self.prefix_tags(self.replace_reserved_chars(tags))
        return " ".join([type, *tags])

    def assert_no_reserved_prefixes(self, all_tokens: list[str]) -> None:
        for reserved_prefix in ["TYPE-", "TAG-"]:
            assert not any(
                t.startswith(reserved_prefix) for t in all_tokens
            ), reserved_prefix

    def replace_reserved_chars(self, all_tokens: list[str]) -> list[str]:
        for reserved in ":&|()":
            all_tokens = [t.replace(reserved, "-") for t in all_tokens]
        return all_tokens

    def prefix_types(self, all_tokens: list[str]) -> list[str]:
        return [f"TYPE-{t}" for t in all_tokens]

    def prefix_tags(self, all_tokens: list[str]) -> list[str]:
        return [f"TAG-{t}" for t in all_tokens]

    def construct_pg_dcb_event(
        self,
        type: str,  # noqa: A002
        data: bytes,
        tags: list[str],
    ) -> PgDCBEvent:
        return self.datastore.psycopg_python_types[PG_TYPE_NAME_DCB_EVENT_TS](
            type, data, tags, self.construct_text_vector(type, tags)
        )


class PgDCBEvent(NamedTuple):
    type: str
    data: bytes
    tags: list[str]
    text_vector: str


class PgDCBEventRow(TypedDict):
    sequence_position: int
    type: str
    data: bytes
    tags: list[str]


class PostgresTSDCBFactory(
    BasePostgresFactory[PostgresTrackingRecorder],
    DCBInfrastructureFactory[PostgresTrackingRecorder],
):
    def dcb_recorder(self) -> DCBRecorder:
        prefix = self.env.name.lower() or "dcb"

        dcb_table_name = prefix + "_events"
        recorder = PostgresDCBRecorderTS(
            datastore=self.datastore,
            events_table_name=dcb_table_name,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder
