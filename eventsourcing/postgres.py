import threading
from itertools import chain
from threading import Event, Timer
from types import TracebackType
from typing import Any, Dict, List, Mapping, Optional, Type
from uuid import UUID

import psycopg2
import psycopg2.errors
import psycopg2.extras
from psycopg2.errorcodes import DUPLICATE_PREPARED_STATEMENT
from psycopg2.extensions import connection, cursor

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
from eventsourcing.utils import retry, strtobool

psycopg2.extras.register_uuid()


class Connection:
    def __init__(self, c: connection, max_age: Optional[float]):
        self.c = c
        self.max_age = max_age
        self.is_idle = Event()
        self.is_closing = Event()
        self.timer: Optional[Timer]
        if max_age is not None:
            self.timer = Timer(interval=max_age, function=self.close_on_timer)
            self.timer.setDaemon(True)
            self.timer.start()
        else:
            self.timer = None
        self.is_prepared: Dict[str, bool] = {}

    def cursor(self) -> cursor:
        return self.c.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def rollback(self) -> None:
        self.c.rollback()

    def commit(self) -> None:
        self.c.commit()

    def close_on_timer(self) -> None:
        self.close()

    def close(self, timeout: Optional[float] = None) -> None:
        if self.timer is not None:
            self.timer.cancel()
        self.is_closing.set()
        self.is_idle.wait(timeout=timeout)
        self.c.close()

    @property
    def is_closed(self) -> bool:
        return self.c.closed


class Transaction:
    # noinspection PyShadowingNames
    def __init__(self, c: Connection, commit: bool):
        self.c = c
        self.commit = commit
        self.has_entered = False

    def __enter__(self) -> "Connection":
        self.has_entered = True
        return self.c

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        try:
            if exc_val:
                self.c.rollback()
                raise exc_val
            elif not self.commit:
                self.c.rollback()
            else:
                self.c.commit()
        except psycopg2.InterfaceError as e:
            self.c.close(timeout=0)
            raise InterfaceError(e)
        except psycopg2.DataError as e:
            raise DataError(e)
        except psycopg2.OperationalError as e:
            raise OperationalError(e)
        except psycopg2.IntegrityError as e:
            raise IntegrityError(e)
        except psycopg2.InternalError as e:
            raise InternalError(e)
        except psycopg2.ProgrammingError as e:
            raise ProgrammingError(e)
        except psycopg2.NotSupportedError as e:
            raise NotSupportedError(e)
        except psycopg2.DatabaseError as e:
            raise DatabaseError(e)
        except psycopg2.Error as e:
            raise PersistenceError(e)
        finally:
            self.c.is_idle.set()

    def __del__(self) -> None:
        if not self.has_entered:
            self.c.is_idle.set()
            raise RuntimeWarning(f"Transaction {self} was not used as context manager")


class PostgresDatastore:
    def __init__(
        self,
        dbname: str,
        host: str,
        port: str,
        user: str,
        password: str,
        conn_max_age: Optional[float] = None,
        pre_ping: bool = False,
        lock_timeout: int = 0,
        idle_in_transaction_session_timeout: int = 0,
    ):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.conn_max_age = conn_max_age
        self.pre_ping = pre_ping
        self.lock_timeout = lock_timeout
        self.idle_in_transaction_session_timeout = idle_in_transaction_session_timeout
        self._connections: Dict[int, Connection] = {}

    def transaction(self, commit: bool) -> Transaction:
        return Transaction(self.get_connection(), commit=commit)

    def get_connection(self) -> Connection:
        thread_id = threading.get_ident()
        try:
            conn = self._connections[thread_id]
        except KeyError:
            conn = self._create_connection(thread_id)
        else:
            conn.is_idle.clear()
            if conn.is_closing.is_set() or conn.is_closed:
                conn = self._create_connection(thread_id)
            elif self.pre_ping:
                try:
                    conn.cursor().execute("SELECT 1")
                except psycopg2.Error:
                    conn = self._create_connection(thread_id)
        return conn

    def _create_connection(self, thread_id: int) -> Connection:
        # Make a connection to a Postgres database.
        try:
            psycopg_c = psycopg2.connect(
                dbname=self.dbname,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                connect_timeout=5,
            )
            psycopg_c.cursor().execute(
                f"SET idle_in_transaction_session_timeout = "
                f"'{self.idle_in_transaction_session_timeout}s'"
            )
        except psycopg2.Error as e:
            raise InterfaceError(e)
        else:
            c = Connection(
                psycopg_c,
                max_age=self.conn_max_age,
            )
            self._connections[thread_id] = c

            return c

    def close_connection(self) -> None:
        thread_id = threading.get_ident()
        try:
            c = self._connections.pop(thread_id)
        except KeyError:
            pass
        else:
            c.close()

    def close_all_connections(self, timeout: Optional[float] = None) -> None:
        for c in self._connections.values():
            c.close(timeout=timeout)
        self._connections.clear()

    def __del__(self) -> None:
        self.close_all_connections(timeout=1)


# noinspection SqlResolve
class PostgresAggregateRecorder(AggregateRecorder):
    def __init__(self, datastore: PostgresDatastore, events_table_name: str):
        self.datastore = datastore
        self.events_table_name = events_table_name
        self.create_table_statements = self.construct_create_table_statements()
        self.insert_events_statement = (
            f"INSERT INTO {self.events_table_name} VALUES ($1, $2, $3, $4)"
        )
        self.insert_events_statement_name = f"insert_{events_table_name}"
        self.select_events_statement = (
            f"SELECT * FROM {self.events_table_name} WHERE originator_id = $1"
        )
        self.lock_statements = [
            f"SET LOCAL lock_timeout = '{self.datastore.lock_timeout}s'",
            f"LOCK TABLE {self.events_table_name} IN EXCLUSIVE MODE",
        ]

    def construct_create_table_statements(self) -> List[str]:
        statement = (
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id uuid NOT NULL, "
            "originator_version integer NOT NULL, "
            "topic text, "
            "state bytea, "
            "PRIMARY KEY "
            "(originator_id, originator_version)) "
            "WITH (autovacuum_enabled=false)"
        )
        return [statement]

    def create_table(self) -> None:
        with self.datastore.transaction(commit=True) as conn:
            with conn.cursor() as c:
                for statement in self.create_table_statements:
                    c.execute(statement)
                pass  # for Coverage 5.5 bug with CPython 3.10.0rc1

    @retry(InterfaceError, max_attempts=10, wait=0.2)
    def insert_events(self, stored_events: List[StoredEvent], **kwargs: Any) -> None:
        self._prepare_insert_events()
        with self.datastore.transaction(commit=True) as conn:
            with conn.cursor() as c:
                self._insert_events(c, stored_events, **kwargs)

    def _prepare_insert_events(self) -> None:
        self._prepare(
            self.insert_events_statement_name,
            self.insert_events_statement,
        )

    def _prepare(self, statement_name: str, statement: str) -> None:
        if not self.datastore.get_connection().is_prepared.get(statement_name):
            with self.datastore.transaction(commit=True) as conn:
                with conn.cursor() as c:
                    try:
                        c.execute(f"PREPARE {statement_name} AS " + statement)
                    except psycopg2.errors.lookup(DUPLICATE_PREPARED_STATEMENT):
                        pass
            conn.is_prepared[statement_name] = True

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        # Acquire "EXCLUSIVE" table lock, to serialize inserts so that
        # insertion of notification IDs is monotonic for notification log
        # readers. We want concurrent transactions to commit inserted
        # notification_id values in order, and by locking the table for writes,
        # it can be guaranteed. The EXCLUSIVE lock mode does not block
        # the ACCESS SHARE lock which is acquired during SELECT statements,
        # so the table can be read concurrently. However INSERT normally
        # just acquires ROW EXCLUSIVE locks, which risks interleaving of
        # many inserts in one transaction with many insert in another
        # transaction. Since one transaction will commit before another,
        # the possibility arises for readers that are tailing a notification
        # log to miss items inserted later but with lower notification IDs.
        # https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-TABLES
        # https://www.postgresql.org/docs/9.1/sql-lock.html
        # https://stackoverflow.com/questions/45866187/guarantee-monotonicity-of
        # -postgresql-serial-column-values-by-commit-order

        len_stored_events = len(stored_events)

        # Just don't do anything if there is nothing to do.
        if len_stored_events == 0:
            return

        # Mogrify the table lock statements.
        lock_sqls = (c.mogrify(s) for s in self.lock_statements)

        # Prepare the commands before getting the table lock.
        page_size = 500
        pages = [
            (
                c.mogrify(
                    f"EXECUTE {self.insert_events_statement_name}(%s, %s, %s, %s)",
                    (
                        stored_event.originator_id,
                        stored_event.originator_version,
                        stored_event.topic,
                        stored_event.state,
                    ),
                )
                for stored_event in page
            )
            for page in (
                stored_events[ndx : min(ndx + page_size, len_stored_events)]
                for ndx in range(0, len_stored_events, page_size)
            )
        ]
        commands = [
            b";".join(page) for page in chain([chain(lock_sqls, pages[0])], pages[1:])
        ]

        # Execute the commands.
        for command in commands:
            c.execute(command)

    @retry(InterfaceError, max_attempts=10, wait=0.2)
    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        parts = [self.select_events_statement]
        params: List[Any] = [originator_id]
        statement_name = f"select_{self.events_table_name}"
        if gt is not None:
            params.append(gt)
            parts.append(f"AND originator_version > ${len(params)}")
            statement_name += "_gt"
        if lte is not None:
            params.append(lte)
            parts.append(f"AND originator_version <= ${len(params)}")
            statement_name += "_lte"
        parts.append("ORDER BY originator_version")
        if desc is False:
            parts.append("ASC")
        else:
            parts.append("DESC")
            statement_name += "_desc"
        if limit is not None:
            params.append(limit)
            parts.append(f"LIMIT ${len(params)}")
            statement_name += "_limit"
        statement = " ".join(parts)
        self._prepare(statement_name, statement)

        stored_events = []
        with self.datastore.transaction(commit=False) as conn:
            with conn.cursor() as c:
                c.execute(
                    f"EXECUTE {statement_name}({', '.join(['%s' for _ in params])})",
                    params,
                )
                for row in c.fetchall():
                    stored_events.append(
                        StoredEvent(
                            originator_id=row["originator_id"],
                            originator_version=row["originator_version"],
                            topic=row["topic"],
                            state=bytes(row["state"]),
                        )
                    )
                pass  # for Coverage 5.5 bug with CPython 3.10.0rc1
        return stored_events


# noinspection SqlResolve
class PostgresApplicationRecorder(
    PostgresAggregateRecorder,
    ApplicationRecorder,
):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str = "stored_events",
    ):
        super().__init__(datastore, events_table_name)
        self.select_notifications_statement = (
            "SELECT * "
            f"FROM {self.events_table_name} "
            "WHERE notification_id>=$1 "
            "ORDER BY notification_id "
            "LIMIT $2"
        )
        self.select_notifications_statement_name = (
            f"select_notifications_{events_table_name}"
        )

        self.max_notification_id_statement = (
            f"SELECT MAX(notification_id) FROM {self.events_table_name}"
        )
        self.max_notification_id_statement_name = (
            f"max_notification_id_{events_table_name}"
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = [
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id uuid NOT NULL, "
            "originator_version integer NOT NULL, "
            "topic text, "
            "state bytea, "
            "notification_id BIGSERIAL, "
            "PRIMARY KEY "
            "(originator_id, originator_version)) "
            "WITH (autovacuum_enabled=false)",
            f"CREATE UNIQUE INDEX IF NOT EXISTS "
            f"{self.events_table_name}_notification_id_idx "
            f"ON {self.events_table_name} (notification_id ASC);",
        ]
        return statements

    @retry(InterfaceError, max_attempts=10, wait=0.2)
    def select_notifications(self, start: int, limit: int) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """
        statement_name = self.select_notifications_statement_name
        self._prepare(statement_name, self.select_notifications_statement)

        notifications = []
        with self.datastore.transaction(commit=False) as conn:
            with conn.cursor() as c:
                c.execute(
                    f"EXECUTE {statement_name}(%s, %s)",
                    (start, limit),
                )
                for row in c.fetchall():
                    notifications.append(
                        Notification(
                            id=row["notification_id"],
                            originator_id=row["originator_id"],
                            originator_version=row["originator_version"],
                            topic=row["topic"],
                            state=bytes(row["state"]),
                        )
                    )
                pass  # for Coverage 5.5 bug with CPython 3.10.0rc1
        return notifications

    @retry(InterfaceError, max_attempts=10, wait=0.2)
    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """
        statement_name = self.max_notification_id_statement_name
        self._prepare(statement_name, self.max_notification_id_statement)

        with self.datastore.transaction(commit=False) as conn:
            with conn.cursor() as c:
                c.execute(
                    f"EXECUTE {statement_name}",
                )
                max_id = c.fetchone()[0] or 0
        return max_id


class PostgresProcessRecorder(
    PostgresApplicationRecorder,
    ProcessRecorder,
):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str,
        tracking_table_name: str,
    ):
        self.tracking_table_name = tracking_table_name
        super().__init__(datastore, events_table_name)
        self.insert_tracking_statement = (
            f"INSERT INTO {self.tracking_table_name} VALUES ($1, $2)"
        )
        self.insert_tracking_statement_name = f"insert_{tracking_table_name}"
        self.max_tracking_id_statement = (
            "SELECT MAX(notification_id) "
            f"FROM {self.tracking_table_name} "
            "WHERE application_name=$1"
        )
        self.max_tracking_id_statement_name = f"max_tracking_id_{tracking_table_name}"

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.tracking_table_name} ("
            "application_name text, "
            "notification_id int, "
            "PRIMARY KEY "
            "(application_name, notification_id))"
        )
        return statements

    @retry(InterfaceError, max_attempts=10, wait=0.2)
    def max_tracking_id(self, application_name: str) -> int:
        statement_name = self.max_tracking_id_statement_name
        self._prepare(statement_name, self.max_tracking_id_statement)

        with self.datastore.transaction(commit=False) as conn:
            with conn.cursor() as c:
                c.execute(
                    f"EXECUTE {statement_name}(%s)",
                    (application_name,),
                )
                max_id = c.fetchone()[0] or 0
        return max_id

    def _prepare_insert_events(self) -> None:
        super()._prepare_insert_events()
        self._prepare(
            self.insert_tracking_statement_name, self.insert_tracking_statement
        )

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        super()._insert_events(c, stored_events, **kwargs)
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            c.execute(
                f"EXECUTE {self.insert_tracking_statement_name}(%s, %s)",
                (
                    tracking.application_name,
                    tracking.notification_id,
                ),
            )


class Factory(InfrastructureFactory):
    POSTGRES_DBNAME = "POSTGRES_DBNAME"
    POSTGRES_HOST = "POSTGRES_HOST"
    POSTGRES_PORT = "POSTGRES_PORT"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"
    POSTGRES_CONN_MAX_AGE = "POSTGRES_CONN_MAX_AGE"
    POSTGRES_PRE_PING = "POSTGRES_PRE_PING"
    POSTGRES_LOCK_TIMEOUT = "POSTGRES_LOCK_TIMEOUT"
    POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT = (
        "POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT"
    )
    CREATE_TABLE = "CREATE_TABLE"

    def __init__(self, application_name: str, env: Mapping):
        super().__init__(application_name, env)
        dbname = self.getenv(self.POSTGRES_DBNAME)
        if dbname is None:
            raise EnvironmentError(
                "Postgres database name not found "
                "in environment with key "
                f"'{self.POSTGRES_DBNAME}'"
            )

        host = self.getenv(self.POSTGRES_HOST)
        if host is None:
            raise EnvironmentError(
                "Postgres host not found "
                "in environment with key "
                f"'{self.POSTGRES_HOST}'"
            )

        port = self.getenv(self.POSTGRES_PORT) or "5432"

        user = self.getenv(self.POSTGRES_USER)
        if user is None:
            raise EnvironmentError(
                "Postgres user not found "
                "in environment with key "
                f"'{self.POSTGRES_USER}'"
            )

        password = self.getenv(self.POSTGRES_PASSWORD)
        if password is None:
            raise EnvironmentError(
                "Postgres password not found "
                "in environment with key "
                f"'{self.POSTGRES_PASSWORD}'"
            )

        conn_max_age: Optional[float]
        conn_max_age_str = self.getenv(self.POSTGRES_CONN_MAX_AGE)
        if conn_max_age_str is None:
            conn_max_age = None
        elif conn_max_age_str == "":
            conn_max_age = None
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

        pre_ping = strtobool(self.getenv(self.POSTGRES_PRE_PING) or "no")

        lock_timeout_str = self.getenv(self.POSTGRES_LOCK_TIMEOUT) or "0"

        try:
            lock_timeout = int(lock_timeout_str)
        except ValueError:
            raise EnvironmentError(
                f"Postgres environment value for key "
                f"'{self.POSTGRES_LOCK_TIMEOUT}' is invalid. "
                f"If set, an integer or empty string is expected: "
                f"'{lock_timeout_str}'"
            )

        idle_in_transaction_session_timeout_str = (
            self.getenv(self.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT) or "0"
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

        self.datastore = PostgresDatastore(
            dbname=dbname,
            host=host,
            port=port,
            user=user,
            password=password,
            conn_max_age=conn_max_age,
            pre_ping=pre_ping,
            lock_timeout=lock_timeout,
            idle_in_transaction_session_timeout=idle_in_transaction_session_timeout,
        )

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        prefix = self.application_name.lower() or "stored"
        events_table_name = prefix + "_" + purpose
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name=events_table_name
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def application_recorder(self) -> ApplicationRecorder:
        prefix = self.application_name.lower() or "stored"
        events_table_name = prefix + "_events"
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name=events_table_name
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def process_recorder(self) -> ProcessRecorder:
        prefix = self.application_name.lower() or "stored"
        events_table_name = prefix + "_events"
        prefix = self.application_name.lower() or "notification"
        tracking_table_name = prefix + "_tracking"
        recorder = PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            tracking_table_name=tracking_table_name,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def env_create_table(self) -> bool:
        default = "yes"
        return bool(strtobool(self.getenv(self.CREATE_TABLE) or default))
