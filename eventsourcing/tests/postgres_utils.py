import psycopg2

from eventsourcing.persistence import PersistenceError
from eventsourcing.postgres import PostgresDatastore


def pg_close_all_connections(
    name="eventsourcing",
    host="127.0.0.1",
    port="5432",
    user="postgres",
    password="postgres",
):
    try:
        # For local development... probably.
        pg_conn = psycopg2.connect(
            dbname=name,
            host=host,
            port=port,
        )
    except psycopg2.Error:
        # For GitHub actions.
        """CREATE ROLE postgres LOGIN SUPERUSER PASSWORD 'postgres';"""
        pg_conn = psycopg2.connect(
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
    return close_all_connections, pg_conn_cursor


def drop_postgres_table(datastore: PostgresDatastore, table_name):
    statement = f"DROP TABLE {table_name};"
    try:
        with datastore.transaction(commit=True) as curs:
            curs.execute(statement)
    except PersistenceError:
        pass
