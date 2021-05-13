import threading
from distutils.util import strtobool
from types import TracebackType
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

import psycopg2
import psycopg2.errors
import psycopg2.extras
from psycopg2.extensions import connection, cursor

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    Notification,
    OperationalError,
    ProcessRecorder,
    RecordConflictError,
    StoredEvent,
    Tracking,
)

psycopg2.extras.register_uuid()


class PostgresDatastore:
    def __init__(self, dbname: str, host: str, port: str, user: str, password: str):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connections: Dict[int, connection] = {}

    def get_connection(self) -> connection:
        thread_id = threading.get_ident()
        try:
            return self.connections[thread_id]
        except KeyError:
            c = self.create_connection()
            self.connections[thread_id] = c
            return c

    def create_connection(self) -> connection:
        # Make a connection to a Postgres database.
        c = psycopg2.connect(
            dbname=self.dbname,
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
        )
        return c

    class Transaction:
        # noinspection PyShadowingNames
        def __init__(self, connection: connection):
            self.c = connection

        def __enter__(self) -> cursor:
            return self.c.cursor(cursor_factory=psycopg2.extras.DictCursor)

        def __exit__(
            self,
            exc_type: Type[BaseException],
            exc_val: BaseException,
            exc_tb: TracebackType,
        ) -> None:
            if exc_type:
                # Roll back all changes
                # if an exception occurs.
                self.c.rollback()
            else:
                self.c.commit()

    def transaction(self) -> Transaction:
        return self.Transaction(self.get_connection())


# noinspection SqlResolve
class PostgresAggregateRecorder(AggregateRecorder):
    def __init__(self, datastore: PostgresDatastore, events_table_name: str):
        self.datastore = datastore
        self.events_table_name = events_table_name
        self.create_table_statements = self.construct_create_table_statements()
        self.insert_events_statement = (
            f"INSERT INTO {self.events_table_name} VALUES (%s, %s, %s, %s)"
        )
        self.select_events_statement = (
            f"SELECT * FROM {self.events_table_name} WHERE originator_id = %s "
        )

    def construct_create_table_statements(self) -> List[str]:
        statement = (
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id uuid NOT NULL, "
            "originator_version integer NOT NULL, "
            "topic text, "
            "state bytea, "
            "PRIMARY KEY "
            "(originator_id, originator_version))"
        )
        return [statement]

    def create_table(self) -> None:
        with self.datastore.transaction() as c:
            try:
                for statement in self.create_table_statements:
                    c.execute(statement)
            except psycopg2.Error as e:
                raise OperationalError(e)

    def insert_events(self, stored_events: List[StoredEvent], **kwargs: Any) -> None:
        with self.datastore.transaction() as c:
            try:
                self._insert_events(c, stored_events, **kwargs)
            except psycopg2.IntegrityError as e:
                raise RecordConflictError(e)
            except psycopg2.Error as e:
                raise OperationalError(e)

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        params = []
        for stored_event in stored_events:
            params.append(
                (
                    stored_event.originator_id,
                    stored_event.originator_version,
                    stored_event.topic,
                    stored_event.state,
                )
            )
        c.executemany(self.insert_events_statement, params)

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
            statement += "AND originator_version > %s "
            params.append(gt)
        if lte is not None:
            statement += "AND originator_version <= %s "
            params.append(lte)
        statement += "ORDER BY originator_version "
        if desc is False:
            statement += "ASC "
        else:
            statement += "DESC "
        if limit is not None:
            statement += "LIMIT %s "
            params.append(limit)
        # statement += ";"
        stored_events = []
        try:
            with self.datastore.transaction() as c:
                c.execute(statement, params)
                for row in c.fetchall():
                    stored_events.append(
                        StoredEvent(
                            originator_id=row["originator_id"],
                            originator_version=row["originator_version"],
                            topic=row["topic"],
                            state=bytes(row["state"]),
                        )
                    )
        except psycopg2.Error as e:
            raise OperationalError(e)
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
        self.statement_notifications_statement = (
            "SELECT * "
            f"FROM {self.events_table_name} "
            "WHERE notification_id>=%s "
            "ORDER BY notification_id "
            "LIMIT %s"
        )
        self.select_max_notification_id_statement = (
            f"SELECT MAX(notification_id) FROM {self.events_table_name}"
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = [
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table_name} ("
            "originator_id uuid NOT NULL, "
            "originator_version integer NOT NULL, "
            "topic text, "
            "state bytea, "
            "notification_id SERIAL, "
            "PRIMARY KEY "
            "(originator_id, originator_version))",
            f"CREATE UNIQUE INDEX IF NOT EXISTS "
            f"{self.events_table_name}_notification_id_idx "
            f"ON {self.events_table_name} (notification_id ASC);",
        ]
        return statements

    def select_notifications(self, start: int, limit: int) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """
        params = [start, limit]
        try:
            with self.datastore.transaction() as c:
                c.execute(self.statement_notifications_statement, params)
                notifications = []
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
        except psycopg2.Error as e:
            raise OperationalError(e)
        return notifications

    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """
        try:
            with self.datastore.transaction() as c:
                c.execute(self.select_max_notification_id_statement)
                return c.fetchone()[0] or 0
        except psycopg2.Error as e:
            raise OperationalError(e)


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

    def max_tracking_id(self, application_name: str) -> int:
        params = [application_name]
        statement = (
            "SELECT MAX(notification_id) "
            f"FROM {self.tracking_table_name} "
            "WHERE application_name=%s"
        )
        try:
            with self.datastore.transaction() as c:
                c.execute(statement, params)
                return c.fetchone()[0] or 0
        except psycopg2.Error as e:
            raise OperationalError(e)

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        super()._insert_events(c, stored_events, **kwargs)
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            statement = f"INSERT INTO {self.tracking_table_name} " "VALUES (%s, %s)"
            c.execute(
                statement,
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
    CREATE_TABLE = "CREATE_TABLE"

    def __init__(self, application_name: str):
        super().__init__(application_name)
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
        self.datastore = PostgresDatastore(
            dbname=dbname,
            host=host,
            port=port,
            user=user,
            password=password,
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
        return bool(strtobool(self.getenv(self.CREATE_TABLE, default) or default))
