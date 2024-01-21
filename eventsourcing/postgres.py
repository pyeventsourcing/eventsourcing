from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union
from uuid import UUID

import psycopg
import psycopg.errors
from psycopg import Connection, Cursor
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    DatabaseError,
    DataError,
    InfrastructureFactory,
    IntegrityError,
    InterfaceError,
    InternalError,
    Notification,
    NotSupportedError,
    OperationalError,
    PersistenceError,
    ProcessRecorder,
    ProgrammingError,
    StoredEvent,
    Tracking,
)
from eventsourcing.utils import Environment, retry, strtobool

logging.getLogger("psycopg.pool").setLevel(logging.CRITICAL)
logging.getLogger("psycopg").setLevel(logging.CRITICAL)


class PostgresDatastore:
    def __init__(
        self,
        dbname: str,
        host: str,
        port: str,
        user: str,
        password: str,
        connect_timeout: int = 5,
        idle_in_transaction_session_timeout: int = 0,
        pool_size: int = 2,
        max_overflow: int = 2,
        pool_timeout: float = 5.0,
        conn_max_age: float = 60 * 60.0,
        pre_ping: bool = False,
        lock_timeout: int = 0,
        schema: str = "",
        pool_open_timeout: Optional[int] = None,
    ):
        self.idle_in_transaction_session_timeout = idle_in_transaction_session_timeout
        self.pre_ping = pre_ping
        self.pool_open_timeout = pool_open_timeout

        if sys.version_info[:2] >= (3, 8):  # pragma: no cover
            check = ConnectionPool.check_connection if pre_ping else None
            kwargs: Dict[str, Any] = {"check": check}
        else:  # pragma: no cover
            # The 'check' argument and the check_connection() method aren't supported.
            kwargs: Dict[str, Any] = {}
        self.pool = ConnectionPool(
            connection_class=Connection[DictRow],
            kwargs={
                "dbname": dbname,
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "row_factory": dict_row,
            },
            min_size=pool_size,
            max_size=pool_size + max_overflow,
            open=False,
            configure=self.after_connect,
            timeout=connect_timeout,
            max_waiting=round(pool_timeout),
            max_lifetime=conn_max_age,
            **kwargs,  # use the 'check' argument when no longer supporting Python 3.7
        )
        self.lock_timeout = lock_timeout
        self.schema = schema.strip()

    def after_connect(self, conn: Connection[DictRow]) -> None:
        conn.autocommit = True
        conn.cursor().execute(
            f"SET idle_in_transaction_session_timeout = "
            f"'{self.idle_in_transaction_session_timeout}s'"
        )

    @contextmanager
    def get_connection(self) -> Iterator[Connection[DictRow]]:
        try:
            wait = self.pool_open_timeout is not None
            timeout = self.pool_open_timeout or 30.0
            self.pool.open(wait, timeout)

            with self.pool.connection() as conn:
                yield conn
        except psycopg.InterfaceError as e:
            # conn.close()
            raise InterfaceError(str(e)) from e
        except psycopg.OperationalError as e:
            # conn.close()
            raise OperationalError(str(e)) from e
        except psycopg.DataError as e:
            raise DataError(str(e)) from e
        except psycopg.IntegrityError as e:
            raise IntegrityError(str(e)) from e
        except psycopg.InternalError as e:
            raise InternalError(str(e)) from e
        except psycopg.ProgrammingError as e:
            raise ProgrammingError(str(e)) from e
        except psycopg.NotSupportedError as e:
            raise NotSupportedError(str(e)) from e
        except psycopg.DatabaseError as e:
            raise DatabaseError(str(e)) from e
        except psycopg.Error as e:
            # conn.close()
            raise PersistenceError(str(e)) from e
        except Exception:
            # conn.close()
            raise

    @contextmanager
    def transaction(self, commit: bool = False) -> Iterator[Cursor[DictRow]]:
        conn: Connection[DictRow]
        with self.get_connection() as conn:
            with conn.transaction(force_rollback=not commit):
                yield conn.cursor()

    def close(self) -> None:
        self.pool.close()

    def __del__(self) -> None:
        self.close()


class PostgresAggregateRecorder(AggregateRecorder):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str,
    ):
        self.check_table_name_length(events_table_name, datastore.schema)
        self.datastore = datastore
        self.events_table_name = events_table_name
        # Index names can't be qualified names, but
        # are created in the same schema as the table.
        if "." in self.events_table_name:
            unqualified_table_name = self.events_table_name.split(".")[-1]
        else:
            unqualified_table_name = self.events_table_name
        self.notification_id_index_name = (
            f"{unqualified_table_name}_notification_id_idx "
        )

        self.create_table_statements = self.construct_create_table_statements()
        self.insert_events_statement = (
            f"INSERT INTO {self.events_table_name} VALUES (%s, %s, %s, %s)"
        )
        self.select_events_statement = (
            f"SELECT * FROM {self.events_table_name} WHERE originator_id = %s"
        )
        self.lock_table_statements: List[str] = []

    @staticmethod
    def check_table_name_length(table_name: str, schema_name: str) -> None:
        schema_prefix = schema_name + "."
        if table_name.startswith(schema_prefix):
            unqualified_table_name = table_name[len(schema_prefix) :]
        else:
            unqualified_table_name = table_name
        if len(unqualified_table_name) > 63:
            raise ProgrammingError(f"Table name too long: {unqualified_table_name}")

    def construct_create_table_statements(self) -> List[str]:
        statement = (
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id uuid NOT NULL, "
            "originator_version bigint NOT NULL, "
            "topic text, "
            "state bytea, "
            "PRIMARY KEY "
            "(originator_id, originator_version)) "
            "WITH (autovacuum_enabled=false)"
        )
        return [statement]

    def create_table(self) -> None:
        with self.datastore.transaction(commit=True) as curs:
            for statement in self.create_table_statements:
                curs.execute(statement, prepare=False)

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        conn: Connection[DictRow]
        exc: Optional[Exception] = None
        notification_ids: Optional[Sequence[int]] = None
        with self.datastore.get_connection() as conn:
            with conn.pipeline() as pipeline:
                with conn.transaction():
                    # Do other things first, so they can be pipelined too.
                    with conn.cursor() as curs:
                        self._insert_events(curs, stored_events, **kwargs)
                    # Then use a different cursor for the executemany() call.
                    with conn.cursor() as curs:
                        try:
                            self._insert_stored_events(curs, stored_events, **kwargs)
                            # Sync now, so any uniqueness constraint violation causes an
                            # IntegrityError to be raised here, rather an InternalError
                            # being raised sometime later e.g. when commit() is called.
                            pipeline.sync()
                            notification_ids = self._fetch_ids_after_insert_events(
                                curs, stored_events, **kwargs
                            )
                        except Exception as e:
                            # Avoid psycopg emitting a pipeline warning.
                            exc = e
            if exc:
                # Reraise exception after pipeline context manager has exited.
                raise exc
        return notification_ids

    def _insert_events(
        self,
        c: Cursor[DictRow],
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        pass

    def _insert_stored_events(
        self,
        c: Cursor[DictRow],
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        # Only do something if there is something to do.
        if len(stored_events) > 0:
            self._lock_table(c)

            # Insert events.
            c.executemany(
                query=self.insert_events_statement,
                params_seq=[
                    (
                        stored_event.originator_id,
                        stored_event.originator_version,
                        stored_event.topic,
                        stored_event.state,
                    )
                    for stored_event in stored_events
                ],
                returning="RETURNING" in self.insert_events_statement,
            )

    def _lock_table(self, c: Cursor[DictRow]) -> None:
        pass

    def _fetch_ids_after_insert_events(
        self,
        c: Cursor[DictRow],
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        return None

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        statement = self.select_events_statement
        params: List[Any] = [originator_id]
        if gt is not None:
            params.append(gt)
            statement += " AND originator_version > %s"
        if lte is not None:
            params.append(lte)
            statement += " AND originator_version <= %s"
        statement += " ORDER BY originator_version"
        if desc is False:
            statement += " ASC"
        else:
            statement += " DESC"
        if limit is not None:
            params.append(limit)
            statement += " LIMIT %s"

        stored_events = []

        with self.datastore.get_connection() as conn:
            with conn.cursor() as curs:
                curs.execute(statement, params, prepare=True)
                for row in curs.fetchall():
                    stored_events.append(
                        StoredEvent(
                            originator_id=row["originator_id"],
                            originator_version=row["originator_version"],
                            topic=row["topic"],
                            state=bytes(row["state"]),
                        )
                    )
        return stored_events


class PostgresApplicationRecorder(PostgresAggregateRecorder, ApplicationRecorder):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str = "stored_events",
    ):
        super().__init__(datastore, events_table_name)
        self.insert_events_statement += " RETURNING notification_id"
        self.max_notification_id_statement = (
            f"SELECT MAX(notification_id) FROM {self.events_table_name}"
        )
        self.lock_table_statements = [
            f"SET LOCAL lock_timeout = '{self.datastore.lock_timeout}s'",
            f"LOCK TABLE {self.events_table_name} IN EXCLUSIVE MODE",
        ]

    def construct_create_table_statements(self) -> List[str]:
        statements = [
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id uuid NOT NULL, "
            "originator_version bigint NOT NULL, "
            "topic text, "
            "state bytea, "
            "notification_id bigserial, "
            "PRIMARY KEY "
            "(originator_id, originator_version)) "
            "WITH (autovacuum_enabled=false)",
            f"CREATE UNIQUE INDEX IF NOT EXISTS "
            f"{self.notification_id_index_name}"
            f"ON {self.events_table_name} (notification_id ASC);",
        ]
        return statements

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def select_notifications(
        self,
        start: int,
        limit: int,
        stop: Optional[int] = None,
        topics: Sequence[str] = (),
    ) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """

        params: List[Union[int, str, Sequence[str]]] = [start]
        statement = f"SELECT * FROM {self.events_table_name} WHERE notification_id>=%s"

        if stop is not None:
            params.append(stop)
            statement += " AND notification_id <= %s"

        if topics:
            params.append(topics)
            statement += " AND topic = ANY(%s)"

        params.append(limit)
        statement += " ORDER BY notification_id LIMIT %s"

        notifications = []
        conn: Connection[DictRow]
        with self.datastore.get_connection() as conn:
            with conn.cursor() as curs:
                curs.execute(statement, params, prepare=True)
                for row in curs.fetchall():
                    notifications.append(
                        Notification(
                            id=row["notification_id"],
                            originator_id=row["originator_id"],
                            originator_version=row["originator_version"],
                            topic=row["topic"],
                            state=bytes(row["state"]),
                        )
                    )
        return notifications

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """
        conn: Connection[DictRow]
        with self.datastore.get_connection() as conn:
            with conn.cursor() as curs:
                curs.execute(self.max_notification_id_statement)
                fetchone = curs.fetchone()
                assert fetchone is not None
                max_id = fetchone["max"] or 0
        return max_id

    def _lock_table(self, c: Cursor[DictRow]) -> None:
        # Acquire "EXCLUSIVE" table lock, to serialize transactions that insert
        # stored events, so that readers don't pass over gaps that are filled in
        # later. We want each transaction that will be issued with notifications
        # IDs by the notification ID sequence to receive all its notification IDs
        # and then commit, before another transaction is issued with any notification
        # IDs. In other words, we want the insert order to be the same as the commit
        # order. We can accomplish this by locking the table for writes. The
        # EXCLUSIVE lock mode does not block SELECT statements, which acquire an
        # ACCESS SHARE lock, so the stored events table can be read concurrently
        # with writes and other reads. However, INSERT statements normally just
        # acquires ROW EXCLUSIVE locks, which risks the interleaving (within the
        # recorded sequence of notification IDs) of stored events from one transaction
        # with those of another transaction. And since one transaction will always
        # commit before another, the possibility arises when using ROW EXCLUSIVE locks
        # for readers that are tailing a notification log to miss items inserted later
        # but issued with lower notification IDs.
        # https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-TABLES
        # https://www.postgresql.org/docs/9.1/sql-lock.html
        # https://stackoverflow.com/questions/45866187/guarantee-monotonicity-of
        # -postgresql-serial-column-values-by-commit-order
        for lock_statement in self.lock_table_statements:
            c.execute(lock_statement, prepare=True)

    def _fetch_ids_after_insert_events(
        self,
        c: Cursor[DictRow],
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        notification_ids: List[int] = []
        len_events = len(stored_events)
        if len_events:
            if (
                (c.statusmessage == "SET")
                and c.nextset()
                and (c.statusmessage == "LOCK TABLE")
            ):
                while c.nextset() and len(notification_ids) != len_events:
                    row = c.fetchone()
                    assert row is not None
                    notification_ids.append(row["notification_id"])
            if len(notification_ids) != len(stored_events):
                raise ProgrammingError("Couldn't get all notification IDs")
        return notification_ids


class PostgresProcessRecorder(PostgresApplicationRecorder, ProcessRecorder):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str,
        tracking_table_name: str,
    ):
        self.check_table_name_length(tracking_table_name, datastore.schema)
        self.tracking_table_name = tracking_table_name
        super().__init__(datastore, events_table_name)
        self.insert_tracking_statement = (
            f"INSERT INTO {self.tracking_table_name} VALUES (%s, %s)"
        )
        self.max_tracking_id_statement = (
            "SELECT MAX(notification_id) "
            f"FROM {self.tracking_table_name} "
            "WHERE application_name=%s"
        )
        self.count_tracking_id_statement = (
            "SELECT COUNT(*) "
            f"FROM {self.tracking_table_name} "
            "WHERE application_name=%s AND notification_id=%s"
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.tracking_table_name} ("
            "application_name text, "
            "notification_id bigint, "
            "PRIMARY KEY "
            "(application_name, notification_id))"
        )
        return statements

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def max_tracking_id(self, application_name: str) -> int:
        with self.datastore.get_connection() as conn:
            with conn.cursor() as curs:
                curs.execute(
                    query=self.max_tracking_id_statement,
                    params=(application_name,),
                    prepare=True,
                )
                fetchone = curs.fetchone()
                assert fetchone is not None
                max_id = fetchone["max"] or 0
        return max_id

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def has_tracking_id(self, application_name: str, notification_id: int) -> bool:
        conn: Connection[DictRow]
        with self.datastore.get_connection() as conn:
            with conn.cursor() as curs:
                curs.execute(
                    query=self.count_tracking_id_statement,
                    params=(application_name, notification_id),
                    prepare=True,
                )
                fetchone = curs.fetchone()
                assert fetchone is not None
                return bool(fetchone["count"])

    def _insert_events(
        self,
        c: Cursor[DictRow],
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            c.execute(
                query=self.insert_tracking_statement,
                params=(
                    tracking.application_name,
                    tracking.notification_id,
                ),
                prepare=True,
            )
        super()._insert_events(c, stored_events, **kwargs)


class Factory(InfrastructureFactory):
    POSTGRES_DBNAME = "POSTGRES_DBNAME"
    POSTGRES_HOST = "POSTGRES_HOST"
    POSTGRES_PORT = "POSTGRES_PORT"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"
    POSTGRES_CONNECT_TIMEOUT = "POSTGRES_CONNECT_TIMEOUT"
    POSTGRES_CONN_MAX_AGE = "POSTGRES_CONN_MAX_AGE"
    POSTGRES_PRE_PING = "POSTGRES_PRE_PING"
    POSTGRES_POOL_TIMEOUT = "POSTGRES_POOL_TIMEOUT"
    POSTGRES_LOCK_TIMEOUT = "POSTGRES_LOCK_TIMEOUT"
    POSTGRES_POOL_SIZE = "POSTGRES_POOL_SIZE"
    POSTGRES_POOL_MAX_OVERFLOW = "POSTGRES_POOL_MAX_OVERFLOW"
    POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT = (
        "POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT"
    )
    POSTGRES_SCHEMA = "POSTGRES_SCHEMA"
    CREATE_TABLE = "CREATE_TABLE"

    aggregate_recorder_class = PostgresAggregateRecorder
    application_recorder_class = PostgresApplicationRecorder
    process_recorder_class = PostgresProcessRecorder

    def __init__(self, env: Environment):
        super().__init__(env)
        dbname = self.env.get(self.POSTGRES_DBNAME)
        if dbname is None:
            raise EnvironmentError(
                "Postgres database name not found "
                "in environment with key "
                f"'{self.POSTGRES_DBNAME}'"
            )

        host = self.env.get(self.POSTGRES_HOST)
        if host is None:
            raise EnvironmentError(
                "Postgres host not found "
                "in environment with key "
                f"'{self.POSTGRES_HOST}'"
            )

        port = self.env.get(self.POSTGRES_PORT) or "5432"

        user = self.env.get(self.POSTGRES_USER)
        if user is None:
            raise EnvironmentError(
                "Postgres user not found "
                "in environment with key "
                f"'{self.POSTGRES_USER}'"
            )

        password = self.env.get(self.POSTGRES_PASSWORD)
        if password is None:
            raise EnvironmentError(
                "Postgres password not found "
                "in environment with key "
                f"'{self.POSTGRES_PASSWORD}'"
            )

        connect_timeout: Optional[int]
        connect_timeout_str = self.env.get(self.POSTGRES_CONNECT_TIMEOUT)
        if connect_timeout_str is None:
            connect_timeout = 5
        elif connect_timeout_str == "":
            connect_timeout = 5
        else:
            try:
                connect_timeout = int(connect_timeout_str)
            except ValueError:
                raise EnvironmentError(
                    f"Postgres environment value for key "
                    f"'{self.POSTGRES_CONNECT_TIMEOUT}' is invalid. "
                    f"If set, an integer or empty string is expected: "
                    f"'{connect_timeout_str}'"
                )

        idle_in_transaction_session_timeout_str = (
            self.env.get(self.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT) or "5"
        )

        try:
            idle_in_transaction_session_timeout = int(
                idle_in_transaction_session_timeout_str
            )
        except ValueError:
            raise EnvironmentError(
                f"Postgres environment value for key "
                f"'{self.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT}' is invalid. "
                f"If set, an integer or empty string is expected: "
                f"'{idle_in_transaction_session_timeout_str}'"
            )

        pool_size: Optional[int]
        pool_size_str = self.env.get(self.POSTGRES_POOL_SIZE)
        if pool_size_str is None:
            pool_size = 5
        elif pool_size_str == "":
            pool_size = 5
        else:
            try:
                pool_size = int(pool_size_str)
            except ValueError:
                raise EnvironmentError(
                    f"Postgres environment value for key "
                    f"'{self.POSTGRES_POOL_SIZE}' is invalid. "
                    f"If set, an integer or empty string is expected: "
                    f"'{pool_size_str}'"
                )

        pool_max_overflow: Optional[int]
        pool_max_overflow_str = self.env.get(self.POSTGRES_POOL_MAX_OVERFLOW)
        if pool_max_overflow_str is None:
            pool_max_overflow = 10
        elif pool_max_overflow_str == "":
            pool_max_overflow = 10
        else:
            try:
                pool_max_overflow = int(pool_max_overflow_str)
            except ValueError:
                raise EnvironmentError(
                    f"Postgres environment value for key "
                    f"'{self.POSTGRES_POOL_MAX_OVERFLOW}' is invalid. "
                    f"If set, an integer or empty string is expected: "
                    f"'{pool_max_overflow_str}'"
                )

        pool_timeout: Optional[float]
        pool_timeout_str = self.env.get(self.POSTGRES_POOL_TIMEOUT)
        if pool_timeout_str is None:
            pool_timeout = 30
        elif pool_timeout_str == "":
            pool_timeout = 30
        else:
            try:
                pool_timeout = float(pool_timeout_str)
            except ValueError:
                raise EnvironmentError(
                    f"Postgres environment value for key "
                    f"'{self.POSTGRES_POOL_TIMEOUT}' is invalid. "
                    f"If set, a float or empty string is expected: "
                    f"'{pool_timeout_str}'"
                )

        conn_max_age: Optional[float]
        DEFAULT_POSTGRES_CONN_MAX_AGE = 60 * 60.0
        conn_max_age_str = self.env.get(self.POSTGRES_CONN_MAX_AGE)
        if conn_max_age_str is None:
            conn_max_age = DEFAULT_POSTGRES_CONN_MAX_AGE
        elif conn_max_age_str == "":
            conn_max_age = DEFAULT_POSTGRES_CONN_MAX_AGE
        else:
            try:
                conn_max_age = float(conn_max_age_str)
            except ValueError:
                raise EnvironmentError(
                    f"Postgres environment value for key "
                    f"'{self.POSTGRES_CONN_MAX_AGE}' is invalid. "
                    f"If set, a float or empty string is expected: "
                    f"'{conn_max_age_str}'"
                )

        pre_ping = strtobool(self.env.get(self.POSTGRES_PRE_PING) or "no")

        lock_timeout_str = self.env.get(self.POSTGRES_LOCK_TIMEOUT) or "0"

        try:
            lock_timeout = int(lock_timeout_str)
        except ValueError:
            raise EnvironmentError(
                f"Postgres environment value for key "
                f"'{self.POSTGRES_LOCK_TIMEOUT}' is invalid. "
                f"If set, an integer or empty string is expected: "
                f"'{lock_timeout_str}'"
            )

        schema = self.env.get(self.POSTGRES_SCHEMA) or ""

        self.datastore = PostgresDatastore(
            dbname=dbname,
            host=host,
            port=port,
            user=user,
            password=password,
            connect_timeout=connect_timeout,
            idle_in_transaction_session_timeout=idle_in_transaction_session_timeout,
            pool_size=pool_size,
            max_overflow=pool_max_overflow,
            pool_timeout=pool_timeout,
            conn_max_age=conn_max_age,
            pre_ping=pre_ping,
            lock_timeout=lock_timeout,
            schema=schema,
        )

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        prefix = self.env.name.lower() or "stored"
        events_table_name = prefix + "_" + purpose
        if self.datastore.schema:
            events_table_name = f"{self.datastore.schema}.{events_table_name}"
        recorder = type(self).aggregate_recorder_class(
            datastore=self.datastore,
            events_table_name=events_table_name,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def application_recorder(self) -> ApplicationRecorder:
        prefix = self.env.name.lower() or "stored"
        events_table_name = prefix + "_events"
        if self.datastore.schema:
            events_table_name = f"{self.datastore.schema}.{events_table_name}"
        recorder = type(self).application_recorder_class(
            datastore=self.datastore,
            events_table_name=events_table_name,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def process_recorder(self) -> ProcessRecorder:
        prefix = self.env.name.lower() or "stored"
        events_table_name = prefix + "_events"
        prefix = self.env.name.lower() or "notification"
        tracking_table_name = prefix + "_tracking"
        if self.datastore.schema:
            events_table_name = f"{self.datastore.schema}.{events_table_name}"
            tracking_table_name = f"{self.datastore.schema}.{tracking_table_name}"
        recorder = type(self).process_recorder_class(
            datastore=self.datastore,
            events_table_name=events_table_name,
            tracking_table_name=tracking_table_name,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def env_create_table(self) -> bool:
        return strtobool(self.env.get(self.CREATE_TABLE) or "yes")

    def close(self) -> None:
        if hasattr(self, "datastore"):
            self.datastore.close()

    def __del__(self) -> None:
        self.close()
