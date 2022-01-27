from contextlib import contextmanager
from itertools import chain
from threading import Lock
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
from eventsourcing.utils import Environment, retry, strtobool

psycopg2.extras.register_uuid()


class PostgresCursor(Cursor):
    def __init__(self, pg_cursor: cursor):
        self.pg_cursor = pg_cursor

    def __enter__(self, *args: Any, **kwargs: Any) -> "PostgresCursor":
        self.pg_cursor.__enter__(*args, **kwargs)
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        return self.pg_cursor.__exit__(*args, **kwargs)

    def mogrify(self, statement: str, params: Any = None) -> bytes:
        return self.pg_cursor.mogrify(statement, vars=params)

    def execute(self, statement: Union[str, bytes], params: Any = None) -> None:
        self.pg_cursor.execute(query=statement, vars=params)

    def fetchall(self) -> Any:
        return self.pg_cursor.fetchall()

    def fetchone(self) -> Any:
        return self.pg_cursor.fetchone()

    @property
    def closed(self) -> bool:
        return self.pg_cursor.closed


class PostgresConnection(Connection[PostgresCursor]):
    def __init__(self, pg_conn: connection, max_age: Optional[float]):
        super().__init__(max_age=max_age)
        self._pg_conn = pg_conn
        self.is_prepared: Set[str] = set()

    @contextmanager
    def transaction(self, commit: bool) -> Iterator[PostgresCursor]:
        # Context managed transaction.
        with PostgresTransaction(self, commit) as curs:
            # Context managed cursor.
            with curs:
                yield curs

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(
            self._pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        )

    def rollback(self) -> None:
        self._pg_conn.rollback()

    def commit(self) -> None:
        self._pg_conn.commit()

    def _close(self) -> None:
        self._pg_conn.close()
        super()._close()

    @property
    def closed(self) -> bool:
        return self._pg_conn.closed


class PostgresConnectionPool(ConnectionPool[PostgresConnection]):
    def __init__(
        self,
        dbname: str,
        host: str,
        port: str,
        user: str,
        password: str,
        connect_timeout: int = 5,
        idle_in_transaction_session_timeout: int = 0,
        pool_size: int = 1,
        max_overflow: int = 0,
        pool_timeout: float = 5.0,
        max_age: Optional[float] = None,
        pre_ping: bool = False,
    ):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connect_timeout = connect_timeout
        self.idle_in_transaction_session_timeout = idle_in_transaction_session_timeout
        super().__init__(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            max_age=max_age,
            pre_ping=pre_ping,
            mutually_exclusive_read_write=False,
        )

    def _create_connection(self) -> PostgresConnection:
        # Make a connection to a database.
        try:
            pg_conn = psycopg2.connect(
                dbname=self.dbname,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                connect_timeout=self.connect_timeout,
            )
        except psycopg2.OperationalError as e:
            raise OperationalError(e) from e
        pg_conn.cursor().execute(
            f"SET idle_in_transaction_session_timeout = "
            f"'{self.idle_in_transaction_session_timeout}s'"
        )
        return PostgresConnection(pg_conn, max_age=self.max_age)


class PostgresTransaction:
    # noinspection PyShadowingNames
    def __init__(self, conn: PostgresConnection, commit: bool):
        self.conn = conn
        self.commit = commit
        self.has_entered = False

    def __enter__(self) -> PostgresCursor:
        self.has_entered = True
        return self.conn.cursor()

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        try:
            if exc_val:
                self.conn.rollback()
                raise exc_val
            elif not self.commit:
                self.conn.rollback()
            else:
                self.conn.commit()
        except psycopg2.InterfaceError as e:
            self.conn.close()
            raise InterfaceError(str(e)) from e
        except psycopg2.DataError as e:
            raise DataError(str(e)) from e
        except psycopg2.OperationalError as e:
            self.conn.close()
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
        conn_max_age: Optional[float] = None,
        pre_ping: bool = False,
        lock_timeout: int = 0,
        schema: str = "",
    ):
        self.pool = PostgresConnectionPool(
            dbname=dbname,
            host=host,
            port=port,
            user=user,
            password=password,
            connect_timeout=connect_timeout,
            idle_in_transaction_session_timeout=idle_in_transaction_session_timeout,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            max_age=conn_max_age,
            pre_ping=pre_ping,
        )
        self.lock_timeout = lock_timeout
        self.schema = schema.strip()

    @contextmanager
    def transaction(self, commit: bool) -> Iterator[PostgresCursor]:
        with self.get_connection() as conn:
            with conn.transaction(commit) as curs:
                yield curs

    @contextmanager
    def get_connection(self) -> Iterator[PostgresConnection]:
        conn = self.pool.get_connection()
        try:
            yield conn
        finally:
            self.pool.put_connection(conn)

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
        self.statement_name_aliases_lock = Lock()
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
            f"INSERT INTO {self.events_table_name} VALUES ($1, $2, $3, $4)"
        )
        self.insert_events_statement_name = f"insert_{events_table_name}".replace(
            ".", "_"
        )
        self.select_events_statement = (
            f"SELECT * FROM {self.events_table_name} WHERE originator_id = $1"
        )
        self.lock_statements: List[str] = []

    @staticmethod
    def check_table_name_length(table_name: str, schema_name: str) -> None:
        schema_prefix = schema_name + "."
        if table_name.startswith(schema_prefix):
            unqualified_table_name = table_name[len(schema_prefix) :]
        else:
            unqualified_table_name = table_name
        if len(unqualified_table_name) > 63:
            raise ProgrammingError(f"Table name too long: {unqualified_table_name}")

    def get_statement_alias(self, statement_name: str) -> str:
        try:
            alias = self.statement_name_aliases[statement_name]
        except KeyError:
            with self.statement_name_aliases_lock:
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
                        uid = uuid5(
                            NAMESPACE_URL, f"/statement_names/{statement_name}"
                        ).hex
                        alias = uid
                        for i in range(len(uid)):  # pragma: no cover
                            preserve_end = 21
                            preserve_start = (
                                PG_IDENTIFIER_MAX_LEN - preserve_end - i - 2
                            )
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
    ) -> Optional[Sequence[int]]:
        with self.datastore.get_connection() as conn:
            self._prepare_insert_events(conn)
            with conn.transaction(commit=True) as curs:
                return self._insert_events(curs, stored_events, **kwargs)

    def _prepare_insert_events(self, conn: PostgresConnection) -> None:
        self._prepare(
            conn,
            self.insert_events_statement_name,
            self.insert_events_statement,
        )

    def _prepare(
        self, conn: PostgresConnection, statement_name: str, statement: str
    ) -> str:
        statement_name_alias = self.get_statement_alias(statement_name)
        if statement_name not in conn.is_prepared:
            curs: PostgresCursor
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
        c: PostgresCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
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

        # Only do something if there is something to do.
        if len_stored_events > 0:

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
                b"; ".join(page)
                for page in chain([chain(lock_sqls, pages[0])], pages[1:])
            ]

            # Execute the commands.
            for command in commands:
                c.execute(command)
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
        statement = (
            "SELECT * " f"FROM {self.events_table_name} " "WHERE notification_id>=$1 "
        )
        statement_name = f"select_notifications_{self.events_table_name}".replace(
            ".", "_"
        )

        if stop is not None:
            params.append(stop)
            statement += f"AND notification_id <= ${len(params)} "
            statement_name += "_stop"

        if topics:
            params.append(topics)
            statement += f"AND topic = ANY(${len(params)}) "
            statement_name += "_topics"

        params.append(limit)
        statement += "ORDER BY notification_id " f"LIMIT ${len(params)}"

        notifications = []
        with self.datastore.get_connection() as conn:
            alias = self._prepare(
                conn,
                statement_name,
                statement,
            )
            with conn.transaction(commit=False) as curs:
                curs.execute(
                    f"EXECUTE {alias}({', '.join(['%s' for _ in params])})",
                    params,
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
        c: PostgresCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        super()._insert_events(c, stored_events, **kwargs)
        if stored_events:
            last_notification_id = c.fetchone()[0]
            notification_ids = list(
                range(
                    last_notification_id - len(stored_events) + 1,
                    last_notification_id + 1,
                )
            )
        else:
            notification_ids = []
        return notification_ids


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
        self.check_table_name_length(tracking_table_name, datastore.schema)
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

    def _prepare_insert_events(self, conn: PostgresConnection) -> None:
        super()._prepare_insert_events(conn)
        self._prepare(
            conn, self.insert_tracking_statement_name, self.insert_tracking_statement
        )

    def _insert_events(
        self,
        c: PostgresCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        notification_ids = super()._insert_events(c, stored_events, **kwargs)
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
        return notification_ids


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
