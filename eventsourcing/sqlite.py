from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, List, Sequence, Type
from uuid import UUID

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    Connection,
    ConnectionPool,
    Cursor,
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
from eventsourcing.utils import Environment, strtobool

if TYPE_CHECKING:  # pragma: nocover
    from types import TracebackType

SQLITE3_DEFAULT_LOCK_TIMEOUT = 5


class SQLiteCursor(Cursor):
    def __init__(self, sqlite_cursor: sqlite3.Cursor):
        self.sqlite_cursor = sqlite_cursor

    def __enter__(self) -> sqlite3.Cursor:
        return self.sqlite_cursor

    def __exit__(self, *args: object, **kwargs: Any) -> None:
        self.sqlite_cursor.close()

    def execute(self, *args: Any, **kwargs: Any) -> None:
        self.sqlite_cursor.execute(*args, **kwargs)

    def executemany(self, *args: Any, **kwargs: Any) -> None:
        self.sqlite_cursor.executemany(*args, **kwargs)

    def fetchall(self) -> Any:
        return self.sqlite_cursor.fetchall()

    def fetchone(self) -> Any:
        return self.sqlite_cursor.fetchone()

    @property
    def lastrowid(self) -> Any:
        return self.sqlite_cursor.lastrowid


class SQLiteConnection(Connection[SQLiteCursor]):
    def __init__(self, sqlite_conn: sqlite3.Connection, max_age: float | None):
        super().__init__(max_age=max_age)
        self._sqlite_conn = sqlite_conn

    @contextmanager
    def transaction(self, *, commit: bool) -> Iterator[SQLiteCursor]:
        # Context managed cursor, and context managed transaction.
        with SQLiteTransaction(self, commit=commit) as curs, curs:
            yield curs

    def cursor(self) -> SQLiteCursor:
        return SQLiteCursor(self._sqlite_conn.cursor())

    def rollback(self) -> None:
        self._sqlite_conn.rollback()

    def commit(self) -> None:
        self._sqlite_conn.commit()

    def _close(self) -> None:
        self._sqlite_conn.close()
        super()._close()


class SQLiteTransaction:
    def __init__(self, connection: SQLiteConnection, *, commit: bool = False):
        self.connection = connection
        self.commit = commit

    def __enter__(self) -> SQLiteCursor:
        # We must issue a "BEGIN" explicitly
        # when running in auto-commit mode.
        cursor = self.connection.cursor()
        cursor.execute("BEGIN")
        return cursor

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_val:
                # Roll back all changes
                # if an exception occurs.
                self.connection.rollback()
                raise exc_val
            if not self.commit:
                self.connection.rollback()
            else:
                self.connection.commit()
        except sqlite3.InterfaceError as e:
            raise InterfaceError(e) from e
        except sqlite3.DataError as e:
            raise DataError(e) from e
        except sqlite3.OperationalError as e:
            raise OperationalError(e) from e
        except sqlite3.IntegrityError as e:
            raise IntegrityError(e) from e
        except sqlite3.InternalError as e:
            raise InternalError(e) from e
        except sqlite3.ProgrammingError as e:
            raise ProgrammingError(e) from e
        except sqlite3.NotSupportedError as e:
            raise NotSupportedError(e) from e
        except sqlite3.DatabaseError as e:
            raise DatabaseError(e) from e
        except sqlite3.Error as e:
            raise PersistenceError(e) from e


class SQLiteConnectionPool(ConnectionPool[SQLiteConnection]):
    def __init__(
        self,
        *,
        db_name: str,
        lock_timeout: int | None = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: float = 5.0,
        max_age: float | None = None,
        pre_ping: bool = False,
    ):
        self.db_name = db_name
        self.lock_timeout = lock_timeout
        self.is_sqlite_memory_mode = self.detect_memory_mode(db_name)
        self.is_journal_mode_wal = False
        self.journal_mode_was_changed_to_wal = False
        super().__init__(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            max_age=max_age,
            pre_ping=pre_ping,
            mutually_exclusive_read_write=self.is_sqlite_memory_mode,
        )

    @staticmethod
    def detect_memory_mode(db_name: str) -> bool:
        return bool(db_name) and (":memory:" in db_name or "mode=memory" in db_name)

    def _create_connection(self) -> SQLiteConnection:
        # Make a connection to an SQLite database.
        try:
            c = sqlite3.connect(
                database=self.db_name,
                uri=True,
                check_same_thread=False,
                isolation_level=None,  # Auto-commit mode.
                cached_statements=True,
                timeout=self.lock_timeout or SQLITE3_DEFAULT_LOCK_TIMEOUT,
            )
        except (sqlite3.Error, TypeError) as e:
            raise InterfaceError(e) from e

        # Use WAL (write-ahead log) mode if file-based database.
        if not self.is_sqlite_memory_mode and not self.is_journal_mode_wal:
            cursor = c.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            if mode.lower() == "wal":
                self.is_journal_mode_wal = True
            else:
                cursor.execute("PRAGMA journal_mode=WAL;")
                self.is_journal_mode_wal = True
                self.journal_mode_was_changed_to_wal = True

        # Set the row factory.
        c.row_factory = sqlite3.Row

        # Return the connection.
        return SQLiteConnection(sqlite_conn=c, max_age=self.max_age)


class SQLiteDatastore:
    def __init__(
        self,
        db_name: str,
        *,
        lock_timeout: int | None = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: float = 5.0,
        max_age: float | None = None,
        pre_ping: bool = False,
    ):
        self.pool = SQLiteConnectionPool(
            db_name=db_name,
            lock_timeout=lock_timeout,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            max_age=max_age,
            pre_ping=pre_ping,
        )

    @contextmanager
    def transaction(self, *, commit: bool) -> Iterator[SQLiteCursor]:
        connection = self.get_connection(commit=commit)
        with connection as conn, conn.transaction(commit=commit) as curs:
            yield curs

    @contextmanager
    def get_connection(self, *, commit: bool) -> Iterator[SQLiteConnection]:
        # Using reader-writer interlocking is necessary for in-memory databases,
        # but also speeds up (and provides "fairness") to file-based databases.
        conn = self.pool.get_connection(is_writer=commit)
        try:
            yield conn
        finally:
            self.pool.put_connection(conn)

    def close(self) -> None:
        self.pool.close()

    def __del__(self) -> None:
        self.close()


class SQLiteAggregateRecorder(AggregateRecorder):
    def __init__(
        self,
        datastore: SQLiteDatastore,
        events_table_name: str = "stored_events",
    ):
        assert isinstance(datastore, SQLiteDatastore)
        self.datastore = datastore
        self.events_table_name = events_table_name
        self.create_table_statements = self.construct_create_table_statements()
        self.insert_events_statement = (
            f"INSERT INTO {self.events_table_name} VALUES (?,?,?,?)"
        )
        self.select_events_statement = (
            f"SELECT * FROM {self.events_table_name} WHERE originator_id=? "
        )

    def construct_create_table_statements(self) -> List[str]:
        statement = (
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id TEXT, "
            "originator_version INTEGER, "
            "topic TEXT, "
            "state BLOB, "
            "PRIMARY KEY "
            "(originator_id, originator_version)) "
            "WITHOUT ROWID"
        )
        return [statement]

    def create_table(self) -> None:
        with self.datastore.transaction(commit=True) as c:
            for statement in self.create_table_statements:
                c.execute(statement)

    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Sequence[int] | None:
        with self.datastore.transaction(commit=True) as c:
            return self._insert_events(c, stored_events, **kwargs)

    def _insert_events(
        self,
        c: SQLiteCursor,
        stored_events: List[StoredEvent],
        **_: Any,
    ) -> Sequence[int] | None:
        params = [
            (
                s.originator_id.hex,
                s.originator_version,
                s.topic,
                s.state,
            )
            for s in stored_events
        ]
        c.executemany(self.insert_events_statement, params)
        return None

    def select_events(
        self,
        originator_id: UUID,
        *,
        gt: int | None = None,
        lte: int | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> List[StoredEvent]:
        statement = self.select_events_statement
        params: List[Any] = [originator_id.hex]
        if gt is not None:
            statement += "AND originator_version>? "
            params.append(gt)
        if lte is not None:
            statement += "AND originator_version<=? "
            params.append(lte)
        statement += "ORDER BY originator_version "
        if desc is False:
            statement += "ASC "
        else:
            statement += "DESC "
        if limit is not None:
            statement += "LIMIT ? "
            params.append(limit)
        with self.datastore.transaction(commit=False) as c:
            c.execute(statement, params)
            return [
                StoredEvent(
                    originator_id=UUID(row["originator_id"]),
                    originator_version=row["originator_version"],
                    topic=row["topic"],
                    state=row["state"],
                )
                for row in c.fetchall()
            ]


class SQLiteApplicationRecorder(
    SQLiteAggregateRecorder,
    ApplicationRecorder,
):
    def __init__(
        self,
        datastore: SQLiteDatastore,
        events_table_name: str = "stored_events",
    ):
        super().__init__(datastore, events_table_name)
        self.select_max_notification_id_statement = (
            f"SELECT MAX(rowid) FROM {self.events_table_name}"
        )

    def construct_create_table_statements(self) -> List[str]:
        statement = (
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id TEXT, "
            "originator_version INTEGER, "
            "topic TEXT, "
            "state BLOB, "
            "PRIMARY KEY "
            "(originator_id, originator_version))"
        )
        return [statement]

    def _insert_events(
        self,
        c: SQLiteCursor,
        stored_events: List[StoredEvent],
        **_: Any,
    ) -> Sequence[int] | None:
        returning = []
        for stored_event in stored_events:
            c.execute(
                self.insert_events_statement,
                (
                    stored_event.originator_id.hex,
                    stored_event.originator_version,
                    stored_event.topic,
                    stored_event.state,
                ),
            )
            returning.append(c.lastrowid)
        return returning

    def select_notifications(
        self,
        start: int,
        limit: int,
        stop: int | None = None,
        topics: Sequence[str] = (),
    ) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """
        params: List[int | str] = [start]
        statement = f"SELECT rowid, * FROM {self.events_table_name} WHERE rowid>=? "

        if stop is not None:
            params.append(stop)
            statement += "AND rowid<=? "

        if topics:
            params += list(topics)
            statement += "AND topic IN (%s) " % ",".join("?" * len(topics))

        params.append(limit)
        statement += "ORDER BY rowid LIMIT ?"

        with self.datastore.transaction(commit=False) as c:
            c.execute(statement, params)
            return [
                Notification(
                    id=row["rowid"],
                    originator_id=UUID(row["originator_id"]),
                    originator_version=row["originator_version"],
                    topic=row["topic"],
                    state=row["state"],
                )
                for row in c.fetchall()
            ]

    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """
        with self.datastore.transaction(commit=False) as c:
            return self._max_notification_id(c)

    def _max_notification_id(self, c: SQLiteCursor) -> int:
        c.execute(self.select_max_notification_id_statement)
        return c.fetchone()[0] or 0


class SQLiteProcessRecorder(
    SQLiteApplicationRecorder,
    ProcessRecorder,
):
    def __init__(
        self,
        datastore: SQLiteDatastore,
        events_table_name: str = "stored_events",
    ):
        super().__init__(datastore, events_table_name)
        self.insert_tracking_statement = "INSERT INTO tracking VALUES (?,?)"
        self.select_max_tracking_id_statement = (
            "SELECT MAX(notification_id) FROM tracking WHERE application_name=?"
        )
        self.count_tracking_id_statement = (
            "SELECT COUNT(*) FROM tracking WHERE "
            "application_name=? AND notification_id=?"
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS tracking ("
            "application_name TEXT, "
            "notification_id INTEGER, "
            "PRIMARY KEY "
            "(application_name, notification_id)) "
            "WITHOUT ROWID"
        )
        return statements

    def max_tracking_id(self, application_name: str) -> int:
        params = [application_name]
        with self.datastore.transaction(commit=False) as c:
            c.execute(self.select_max_tracking_id_statement, params)
            return c.fetchone()[0] or 0

    def has_tracking_id(self, application_name: str, notification_id: int) -> bool:
        params = [application_name, notification_id]
        with self.datastore.transaction(commit=False) as c:
            c.execute(self.count_tracking_id_statement, params)
            return bool(c.fetchone()[0])

    def _insert_events(
        self,
        c: SQLiteCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Sequence[int] | None:
        returning = super()._insert_events(c, stored_events, **kwargs)
        tracking: Tracking | None = kwargs.get("tracking", None)
        if tracking is not None:
            c.execute(
                self.insert_tracking_statement,
                (
                    tracking.application_name,
                    tracking.notification_id,
                ),
            )
        return returning


class Factory(InfrastructureFactory):
    SQLITE_DBNAME = "SQLITE_DBNAME"
    SQLITE_LOCK_TIMEOUT = "SQLITE_LOCK_TIMEOUT"
    CREATE_TABLE = "CREATE_TABLE"

    aggregate_recorder_class = SQLiteAggregateRecorder
    application_recorder_class = SQLiteApplicationRecorder
    process_recorder_class = SQLiteProcessRecorder

    def __init__(self, env: Environment):
        super().__init__(env)
        db_name = self.env.get(self.SQLITE_DBNAME)
        if not db_name:
            msg = (
                "SQLite database name not found "
                "in environment with keys: "
                f"{', '.join(self.env.create_keys(self.SQLITE_DBNAME))}"
            )
            raise OSError(msg)

        lock_timeout_str = (
            self.env.get(self.SQLITE_LOCK_TIMEOUT) or ""
        ).strip() or None

        lock_timeout: int | None = None
        if lock_timeout_str is not None:
            try:
                lock_timeout = int(lock_timeout_str)
            except ValueError:
                msg = (
                    "SQLite environment value for key "
                    f"'{self.SQLITE_LOCK_TIMEOUT}' is invalid. "
                    "If set, an int or empty string is expected: "
                    f"'{lock_timeout_str}'"
                )
                raise OSError(msg) from None

        self.datastore = SQLiteDatastore(db_name=db_name, lock_timeout=lock_timeout)

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        events_table_name = "stored_" + purpose
        recorder = self.aggregate_recorder_class(
            datastore=self.datastore,
            events_table_name=events_table_name,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def application_recorder(self) -> ApplicationRecorder:
        recorder = self.application_recorder_class(datastore=self.datastore)
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def process_recorder(self) -> ProcessRecorder:
        recorder = self.process_recorder_class(datastore=self.datastore)
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def env_create_table(self) -> bool:
        default = "yes"
        return bool(strtobool(self.env.get(self.CREATE_TABLE, default) or default))

    def close(self) -> None:
        self.datastore.close()
