from contextlib import contextmanager
from itertools import chain
from threading import Event, Lock, Timer
from types import TracebackType
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)
from uuid import NAMESPACE_URL, UUID, uuid5

import psycopg2
import psycopg2.errors
import psycopg2.extras
from psycopg2.errorcodes import DUPLICATE_PREPARED_STATEMENT
from psycopg2.extensions import connection, cursor
from psycopg2.pool import PoolError, ThreadedConnectionPool

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

psycopg2.extras.register_uuid()


class Connection:
    def __init__(self, pg_conn: connection, max_age: Optional[float]):
        self._pg_conn = pg_conn
        self._max_age = max_age
        self._is_idle = Event()
        self._is_closing = Event()
        self._close_lock = Lock()
        self._timer: Optional[Timer]
        self._was_closed_by_timer = False
        if max_age is not None:
            self._timer = Timer(interval=max_age, function=self.close_on_timer)
            self._timer.daemon = True
            self._timer.start()
        else:
            self._timer = None
        self.is_prepared: Set[str] = set()

    @contextmanager
    def transaction(self, commit: bool) -> Iterator[cursor]:
        # Context managed transaction.
        with Transaction(self, commit) as curs:
            # Context managed cursor.
            with curs:
                yield curs

    @property
    def info(self) -> Any:
        return self._pg_conn.info

    @property
    def is_idle(self) -> bool:
        return self._is_idle.is_set()

    def set_is_idle(self) -> None:
        self._is_idle.set()

    def set_not_idle(self) -> None:
        self._is_idle.clear()

    def wait_until_idle(self, timeout: Optional[float]) -> None:
        self._is_idle.wait(timeout)

    @property
    def is_closing(self) -> bool:
        return self._is_closing.is_set()

    def cursor(self) -> cursor:
        return self._pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def rollback(self) -> None:
        self._pg_conn.rollback()

    def commit(self) -> None:
        self._pg_conn.commit()

    def close_on_timer(self) -> None:
        self._is_closing.set()
        self.wait_until_idle(timeout=None)
        self._was_closed_by_timer = True
        self.close()

    def set_is_closing(self) -> None:
        self._is_closing.set()

    def close(self) -> None:
        with self._close_lock:
            if self._timer is not None:
                self._timer.cancel()
            self._is_closing.set()
            self._pg_conn.close()

    @property
    def closed(self) -> bool:
        return self._pg_conn.closed

    @property
    def was_closed_by_timer(self) -> bool:
        return self._was_closed_by_timer


class ConnectionPoolClosed(Exception):
    pass


class ConnectionPoolExhaustedError(OperationalError):
    pass


class ConnectionPoolUnkeyedConnectionError(Exception):
    pass


class ConnectionPool(ThreadedConnectionPool):
    def __init__(
        self,
        dbname: str,
        host: str,
        port: str,
        user: str,
        password: str,
        max_age: Optional[float] = None,
        pre_ping: bool = False,
        idle_in_transaction_session_timeout: int = 0,
        min_conn: int = 0,
        max_conn: int = 20,
    ):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.max_age = max_age
        self.pre_ping = pre_ping
        self.idle_in_transaction_session_timeout = idle_in_transaction_session_timeout
        super().__init__(minconn=min_conn, maxconn=max_conn)

    @property
    def max_conn(self) -> int:
        return self.maxconn

    @max_conn.setter
    def max_conn(self, value: int) -> None:
        self.maxconn = value

    @property
    def min_conn(self) -> int:
        return self.minconn

    @min_conn.setter
    def min_conn(self, value: int) -> None:
        self.minconn = value

    def close(self) -> None:
        try:
            self.closeall()
        except PoolError:
            pass

    def get(self) -> Connection:
        return self.getconn()

    def _getconn(self, key: Any = None) -> Connection:
        while True:

            try:
                conn: Connection = super()._getconn(key)
            except PoolError as e:
                # Catch and inspect any 'PoolError' from psycopg2.
                err_str = str(e)

                # If the pool is closed, quit and don't retry.
                if "closed" in err_str:
                    raise ConnectionPoolClosed(err_str) from e

                # If pool exhausted, quit to release lock before retrying.
                assert "exhausted" in err_str
                raise ConnectionPoolExhaustedError(err_str) from e

            # Check for closed or dysfunctional connections.
            if conn.closed or conn.is_closing:
                super()._putconn(conn, close=True)
                continue
            elif self.pre_ping:
                try:
                    conn.cursor().execute("SELECT 1")
                except psycopg2.Error:
                    super()._putconn(conn, close=True)
                    continue

            conn.set_not_idle()
            return conn

    def put(self, conn: Connection, close: bool = False) -> None:
        conn.set_is_idle()
        try:
            return self.putconn(conn, close=close or conn.is_closing)
        except PoolError as e:
            raise ConnectionPoolUnkeyedConnectionError() from e

    def _connect(self, key: Any = None) -> Connection:
        """
        Create a new connection and assign it to 'key' if not None.
        """
        conn = self._create_connection()
        if key is not None:
            self._used[key] = conn
            self._rused[id(conn)] = key
        else:
            self._pool.append(conn)
        return conn

    def _create_connection(self) -> Connection:
        # Make a connection to a database.
        try:
            pg_conn = psycopg2.connect(
                dbname=self.dbname,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                connect_timeout=5,
            )
        except psycopg2.OperationalError as e:
            raise OperationalError(e) from e
        pg_conn.cursor().execute(
            f"SET idle_in_transaction_session_timeout = "
            f"'{self.idle_in_transaction_session_timeout}s'"
        )
        return Connection(pg_conn, max_age=self.max_age)


class Transaction:
    # noinspection PyShadowingNames
    def __init__(self, c: Connection, commit: bool):
        self.c = c
        self.commit = commit
        self.has_entered = False

    def __enter__(self) -> cursor:
        self.has_entered = True
        return self.c.cursor()

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
            self.c.close()
            raise InterfaceError(str(e)) from e
        except psycopg2.DataError as e:
            raise DataError(str(e)) from e
        except psycopg2.OperationalError as e:
            self.c.close()
            raise OperationalError(str(e)) from e
        except psycopg2.IntegrityError as e:
            raise IntegrityError(str(e)) from e
        except psycopg2.InternalError as e:
            raise InternalError(str(e)) from e
        except psycopg2.ProgrammingError as e:
            raise ProgrammingError(str(e)) from e
        except psycopg2.NotSupportedError as e:
            raise NotSupportedError(str(e)) from e
        except psycopg2.DatabaseError as e:
            raise DatabaseError(str(e)) from e
        except psycopg2.Error as e:
            raise PersistenceError(str(e)) from e

    def __del__(self) -> None:
        if not self.has_entered:
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
        min_conn: int = 0,
        max_conn: int = 20,
        schema: str = "",
    ):
        self.pool = ConnectionPool(
            dbname=dbname,
            host=host,
            port=port,
            user=user,
            password=password,
            max_age=conn_max_age,
            pre_ping=pre_ping,
            idle_in_transaction_session_timeout=idle_in_transaction_session_timeout,
            min_conn=min_conn,
            max_conn=max_conn,
        )
        self.lock_timeout = lock_timeout
        self.schema = schema.strip()

    @contextmanager
    def transaction(self, commit: bool) -> Iterator[cursor]:
        with self.get_connection() as conn:
            with conn.transaction(commit) as curs:
                yield curs

    @contextmanager
    def get_connection(self) -> Iterator[Connection]:
        conn: Connection = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    def report_on_prepared_statements(
        self,
    ) -> Tuple[List[List[Union[bool, str]]], List[str]]:
        with self.get_connection() as conn:
            with conn.cursor() as curs:
                curs.execute("SELECT * from pg_prepared_statements")
                return sorted(curs.fetchall()), sorted(conn.is_prepared)

    def close(self) -> None:
        self.pool.close()

    def __del__(self) -> None:
        self.close()


PG_IDENTIFIER_MAX_LEN = 63


# noinspection SqlResolve
class PostgresAggregateRecorder(AggregateRecorder):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str,
    ):
        self.statement_name_aliases: Dict[str, str] = {}
        if len(events_table_name) > PG_IDENTIFIER_MAX_LEN:
            raise ProgrammingError(f"Table name too long: {events_table_name}")
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
            f"INSERT INTO {self.events_table_name} VALUES ($1, $2, $3, $4)"
        )
        self.insert_events_statement_name = f"insert_{events_table_name}".replace(
            ".", "_"
        )
        self.select_events_statement = (
            f"SELECT * FROM {self.events_table_name} WHERE originator_id = $1"
        )
        self.lock_statements: List[str] = []

    def get_statement_alias(self, statement_name: str) -> str:
        try:
            alias = self.statement_name_aliases[statement_name]
        except KeyError:
            existing_aliases = self.statement_name_aliases.values()
            if (
                len(statement_name) <= PG_IDENTIFIER_MAX_LEN
                and statement_name not in existing_aliases
            ):
                alias = statement_name
                self.statement_name_aliases[statement_name] = alias
            else:
                uid = uuid5(NAMESPACE_URL, f"/statement_names/{statement_name}").hex
                alias = uid
                for i in range(len(uid)):  # pragma: no cover
                    preserve_end = 21
                    preserve_start = PG_IDENTIFIER_MAX_LEN - preserve_end - i - 2
                    uuid5_tail = i
                    candidate = (
                        statement_name[:preserve_start]
                        + "_"
                        + (uid[-uuid5_tail:] if i else "")
                        + "_"
                        + statement_name[-preserve_end:]
                    )
                    assert len(alias) <= PG_IDENTIFIER_MAX_LEN
                    if candidate not in existing_aliases:
                        alias = candidate
                        break
                self.statement_name_aliases[statement_name] = alias
        return alias

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
                curs.execute(statement)
            pass  # for Coverage 5.5 bug with CPython 3.10.0rc1

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Sequence[Tuple[StoredEvent, Optional[int]]]:
        with self.datastore.get_connection() as conn:
            self._prepare_insert_events(conn)
            with conn.transaction(commit=True) as curs:
                return self._insert_events(curs, stored_events, **kwargs)

    def _prepare_insert_events(self, conn: Connection) -> None:
        self._prepare(
            conn,
            self.insert_events_statement_name,
            self.insert_events_statement,
        )

    def _prepare(self, conn: Connection, statement_name: str, statement: str) -> str:
        statement_name_alias = self.get_statement_alias(statement_name)
        if statement_name not in conn.is_prepared:
            curs: cursor
            with conn.transaction(commit=True) as curs:
                try:
                    lock_timeout = self.datastore.lock_timeout
                    curs.execute(f"SET LOCAL lock_timeout = '{lock_timeout}s'")
                    curs.execute(f"PREPARE {statement_name_alias} AS " + statement)
                except psycopg2.errors.lookup(DUPLICATE_PREPARED_STATEMENT):
                    pass
                conn.is_prepared.add(statement_name)
        return statement_name_alias

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Sequence[Tuple[StoredEvent, Optional[int]]]:
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

        # Just do nothing here if there is nothing to do.
        if len_stored_events == 0:
            return []

        # Mogrify the table lock statements.
        lock_sqls = (c.mogrify(s) for s in self.lock_statements)

        # Prepare the commands before getting the table lock.
        alias = self.statement_name_aliases[self.insert_events_statement_name]
        page_size = 500
        pages = [
            (
                c.mogrify(
                    f"EXECUTE {alias}(%s, %s, %s, %s)",
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
            b"; ".join(page) for page in chain([chain(lock_sqls, pages[0])], pages[1:])
        ]

        # Execute the commands.
        for command in commands:
            c.execute(command)
        return [(s, None) for s in stored_events]

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
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
        statement_name = f"select_{self.events_table_name}".replace(".", "_")
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

        stored_events = []

        with self.datastore.get_connection() as conn:
            alias = self._prepare(conn, statement_name, statement)

            with conn.transaction(commit=False) as curs:
                curs.execute(
                    f"EXECUTE {alias}({', '.join(['%s' for _ in params])})",
                    params,
                )
                for row in curs.fetchall():
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
        self.insert_events_statement = (
            f"INSERT INTO {self.events_table_name} VALUES ($1, $2, $3, $4) "
            f"RETURNING notification_id"
        )

        self.select_notifications_statement = (
            "SELECT * "
            f"FROM {self.events_table_name} "
            "WHERE notification_id>=$1 "
            "ORDER BY notification_id "
            "LIMIT $2"
        )
        self.select_notifications_statement_name = (
            f"select_notifications_{events_table_name}".replace(".", "_")
        )
        self.select_notifications_filter_topics_statement = (
            "SELECT * "
            f"FROM {self.events_table_name} "
            "WHERE notification_id>=$1 AND topic = ANY($2) "
            "ORDER BY notification_id "
            "LIMIT $3"
        )
        self.select_notifications_filter_topics_statement_name = (
            f"select_notifications_filter_topics_{events_table_name}"
        )

        self.max_notification_id_statement = (
            f"SELECT MAX(notification_id) FROM {self.events_table_name}"
        )
        self.max_notification_id_statement_name = (
            f"max_notification_id_{events_table_name}".replace(".", "_")
        )
        self.lock_statements = [
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
        self, start: int, limit: int, topics: Sequence[str] = ()
    ) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """
        notifications = []
        with self.datastore.get_connection() as conn:
            if topics:
                statement_name = self.select_notifications_filter_topics_statement_name
                statement_alias = self._prepare(
                    conn,
                    statement_name,
                    self.select_notifications_filter_topics_statement,
                )
            else:
                statement_name = self.select_notifications_statement_name
                statement_alias = self._prepare(
                    conn, statement_name, self.select_notifications_statement
                )

            with conn.transaction(commit=False) as curs:
                if topics:
                    curs.execute(
                        f"EXECUTE {statement_alias}(%s, %s, %s)",
                        (start, topics, limit),
                    )
                else:
                    curs.execute(
                        f"EXECUTE {statement_alias}(%s, %s)",
                        (start, limit),
                    )
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
                pass  # for Coverage 5.5 bug with CPython 3.10.0rc1
        return notifications

    @retry((InterfaceError, OperationalError), max_attempts=10, wait=0.2)
    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """
        statement_name = self.max_notification_id_statement_name
        with self.datastore.get_connection() as conn:
            statement_alias = self._prepare(
                conn, statement_name, self.max_notification_id_statement
            )
            with conn.transaction(commit=False) as curs:
                curs.execute(
                    f"EXECUTE {statement_alias}",
                )
                max_id = curs.fetchone()[0] or 0
        return max_id

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Sequence[Tuple[StoredEvent, Optional[int]]]:
        super()._insert_events(c, stored_events, **kwargs)
        if stored_events:
            last_notification_id = c.fetchone()[0]
            notification_ids = list(
                range(
                    last_notification_id - len(stored_events) + 1,
                    last_notification_id + 1,
                )
            )
            returning = [(s, notification_ids[i]) for i, s in enumerate(stored_events)]
        else:
            returning = []
        return returning


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
        if len(tracking_table_name) > 63:
            raise ProgrammingError(f"Table name too long: {tracking_table_name}")

        self.tracking_table_name = tracking_table_name
        super().__init__(datastore, events_table_name)
        self.insert_tracking_statement = (
            f"INSERT INTO {self.tracking_table_name} VALUES ($1, $2)"
        )
        self.insert_tracking_statement_name = f"insert_{tracking_table_name}".replace(
            ".", "_"
        )
        self.max_tracking_id_statement = (
            "SELECT MAX(notification_id) "
            f"FROM {self.tracking_table_name} "
            "WHERE application_name=$1"
        )
        self.max_tracking_id_statement_name = (
            f"max_tracking_id_{tracking_table_name}".replace(".", "_")
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
        statement_name = self.max_tracking_id_statement_name
        with self.datastore.get_connection() as conn:
            statement_alias = self._prepare(
                conn, statement_name, self.max_tracking_id_statement
            )

            with conn.transaction(commit=False) as curs:
                curs.execute(
                    f"EXECUTE {statement_alias}(%s)",
                    (application_name,),
                )
                max_id = curs.fetchone()[0] or 0
        return max_id

    def _prepare_insert_events(self, conn: Connection) -> None:
        super()._prepare_insert_events(conn)
        self._prepare(
            conn, self.insert_tracking_statement_name, self.insert_tracking_statement
        )

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Sequence[Tuple[StoredEvent, Optional[int]]]:
        returning = super()._insert_events(c, stored_events, **kwargs)
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            statement_alias = self.statement_name_aliases[
                self.insert_tracking_statement_name
            ]
            c.execute(
                f"EXECUTE {statement_alias}(%s, %s)",
                (
                    tracking.application_name,
                    tracking.notification_id,
                ),
            )
        return returning


class Factory(InfrastructureFactory):
    POSTGRES_DBNAME = "POSTGRES_DBNAME"
    POSTGRES_HOST = "POSTGRES_HOST"
    POSTGRES_PORT = "POSTGRES_PORT"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"
    POSTGRES_CONN_MAX_AGE = "POSTGRES_CONN_MAX_AGE"
    POSTGRES_PRE_PING = "POSTGRES_PRE_PING"
    POSTGRES_LOCK_TIMEOUT = "POSTGRES_LOCK_TIMEOUT"
    POSTGRES_POOL_MAX_CONN = "POSTGRES_POOL_MAX_CONN"
    POSTGRES_POOL_MIN_CONN = "POSTGRES_POOL_MIN_CONN"
    POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT = (
        "POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT"
    )
    POSTGRES_SCHEMA = "POSTGRES_SCHEMA"
    CREATE_TABLE = "CREATE_TABLE"

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

        conn_max_age: Optional[float]
        conn_max_age_str = self.env.get(self.POSTGRES_CONN_MAX_AGE)
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

        pool_max_conn: Optional[int]
        pool_max_conn_str = self.env.get(self.POSTGRES_POOL_MAX_CONN)
        if pool_max_conn_str is None:
            pool_max_conn = 10
        elif pool_max_conn_str == "":
            pool_max_conn = 10
        else:
            try:
                pool_max_conn = int(pool_max_conn_str)
            except ValueError:
                raise EnvironmentError(
                    f"Postgres environment value for key "
                    f"'{self.POSTGRES_POOL_MAX_CONN}' is invalid. "
                    f"If set, an integer or empty string is expected: "
                    f"'{pool_max_conn_str}'"
                )

        pool_min_conn: Optional[int]
        pool_min_conn_str = self.env.get(self.POSTGRES_POOL_MIN_CONN)
        if pool_min_conn_str is None:
            pool_min_conn = 10
        elif pool_min_conn_str == "":
            pool_min_conn = 10
        else:
            try:
                pool_min_conn = int(pool_min_conn_str)
            except ValueError:
                raise EnvironmentError(
                    f"Postgres environment value for key "
                    f"'{self.POSTGRES_POOL_MIN_CONN}' is invalid. "
                    f"If set, an integer or empty string is expected: "
                    f"'{pool_min_conn_str}'"
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

        idle_in_transaction_session_timeout_str = (
            self.env.get(self.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT) or "0"
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

        schema = self.env.get(self.POSTGRES_SCHEMA) or ""

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
            max_conn=pool_max_conn,
            min_conn=pool_min_conn,
            schema=schema,
        )

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        prefix = self.env.name.lower() or "stored"
        events_table_name = prefix + "_" + purpose
        if self.datastore.schema:
            events_table_name = f"{self.datastore.schema}.{events_table_name}"
        recorder = PostgresAggregateRecorder(
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
        recorder = PostgresApplicationRecorder(
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
        recorder = PostgresProcessRecorder(
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
        self.datastore.close()
