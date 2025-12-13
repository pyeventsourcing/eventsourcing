import os

import psycopg
from psycopg.sql import SQL, Identifier

from eventsourcing.dcb.postgres_tt import (
    DB_FUNCTION_NAME_DCB_CONDITIONAL_APPEND_TT,
    DB_FUNCTION_NAME_DCB_UNCONDITIONAL_APPEND_TT,
    DB_TYPE_NAME_DCB_EVENT_TT,
    DB_TYPE_NAME_DCB_QUERY_ITEM_TT,
)
from eventsourcing.postgres import PostgresDatastore
from examples.dcb_enrolment_with_basic_objects.postgres_ts import (
    PG_FUNCTION_NAME_DCB_CHECK_APPEND_CONDITION_TS,
    PG_FUNCTION_NAME_DCB_INSERT_EVENTS_TS,
    PG_FUNCTION_NAME_DCB_SELECT_EVENTS_TS,
    PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS,
    PG_TYPE_NAME_DCB_EVENT_TS,
)


def pg_close_all_connections(
    name: str = "eventsourcing",
    host: str = "127.0.0.1",
    port: str = "5432",
    user: str = "postgres",
    password: str = "postgres",  # noqa: S107
) -> None:
    try:
        # For local development... probably.
        pg_conn = psycopg.connect(
            dbname=name,
            host=host,
            port=port,
        )
    except psycopg.Error:
        # For GitHub actions.
        """CREATE ROLE postgres LOGIN SUPERUSER PASSWORD 'postgres';"""
        pg_conn = psycopg.connect(
            dbname=name,
            host=host,
            port=port,
            user=user,
            password=password,
        )
    close_all_connections = """
    SELECT
        pg_terminate_backend(pid)
    FROM
        pg_stat_activity
    WHERE
        -- don't kill my own connection!
        pid <> pg_backend_pid();

    """
    pg_conn_cursor = pg_conn.cursor()
    pg_conn_cursor.execute(close_all_connections)


def drop_tables() -> None:

    for schema in ["public", "myschema"]:
        datastore = PostgresDatastore(
            dbname=os.environ.get("POSTGRES_DBNAME", "eventsourcing"),
            host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            user=os.environ.get("POSTGRES_USER", "eventsourcing"),
            password=os.environ.get("POSTGRES_PASSWORD", "eventsourcing"),
            schema=schema,
        )
        with datastore.transaction(commit=True) as curs:
            select_table_names = SQL(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s"
            )
            fetchall = curs.execute(select_table_names, (datastore.schema,)).fetchall()
            for row in fetchall:
                table_name = row["table_name"]
                # print(f"Dropping table '{table_name}' in schema '{schema}'")
                statement = SQL("DROP TABLE IF EXISTS {0}.{1} CASCADE").format(
                    Identifier(datastore.schema), Identifier(table_name)
                )
                curs.execute(statement, prepare=False)
                # print(f"Dropped table '{table_name}' in schema '{schema}'")

            # Also drop composite types.
            composite_types = [
                "stored_event_uuid",
                "stored_event_text",
                PG_TYPE_NAME_DCB_EVENT_TS,
                DB_TYPE_NAME_DCB_EVENT_TT,
                DB_TYPE_NAME_DCB_QUERY_ITEM_TT,
            ]
            for name in composite_types:
                statement = SQL("DROP TYPE IF EXISTS {schema}.{name} CASCADE").format(
                    schema=Identifier(datastore.schema),
                    name=Identifier(name),
                )
                curs.execute(statement, prepare=False)

            # Also drop functions.
            functions = [
                "es_insert_events_uuid",
                "es_insert_events_text",
                PG_FUNCTION_NAME_DCB_INSERT_EVENTS_TS,
                PG_FUNCTION_NAME_DCB_SELECT_EVENTS_TS,
                PG_FUNCTION_NAME_DCB_CHECK_APPEND_CONDITION_TS,
                DB_FUNCTION_NAME_DCB_UNCONDITIONAL_APPEND_TT,
                DB_FUNCTION_NAME_DCB_CONDITIONAL_APPEND_TT,
            ]
            for name in functions:
                statement = SQL(
                    "DROP FUNCTION IF EXISTS {schema}.{name} CASCADE"
                ).format(
                    schema=Identifier(datastore.schema),
                    name=Identifier(name),
                )
                curs.execute(statement, prepare=False)

            # Also drop procedures.
            procedures = [
                PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS,
            ]
            for name in procedures:
                statement = SQL(
                    "DROP PROCEDURE IF EXISTS {schema}.{name} CASCADE"
                ).format(
                    schema=Identifier(datastore.schema),
                    name=Identifier(name),
                )
                curs.execute(statement, prepare=False)
