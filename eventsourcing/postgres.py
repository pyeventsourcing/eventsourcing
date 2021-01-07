import threading
from distutils.util import strtobool
from typing import Any, List, Optional
from uuid import UUID

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection, cursor

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    Notification,
    ProcessRecorder,
    RecordConflictError,
    StoredEvent,
    Tracking,
)

psycopg2.extras.register_uuid()


class PostgresDatabase:
    def __init__(self, dbname, host, user, password):
        self.dbname = dbname
        self.host = host
        self.user = user
        self.password = password
        self.connections = {}

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
            user=self.user,
            password=self.password,
        )
        return c

    class Transaction:
        def __init__(self, connection: connection):
            self.c = connection

        def __enter__(self) -> cursor:
            cursor = self.c.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # cursor.execute("BEGIN")
            return cursor

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                # Roll back all changes
                # if an exception occurs.
                self.c.rollback()
            else:
                self.c.commit()

    def transaction(self) -> Transaction:
        return self.Transaction(self.get_connection())


class PostgresAggregateRecorder(AggregateRecorder):
    def __init__(
        self, application_name: str, db_name: str, host: str, user: str, password: str
    ):
        self.application_name = application_name
        self.db = PostgresDatabase(db_name, host, user, password)
        self.events_table = application_name.lower() + "events"

    def create_table(self):
        with self.db.transaction() as c:
            self._create_table(c)

    def _create_table(self, c: cursor):
        statement = (
            "CREATE TABLE IF NOT EXISTS "
            f"{self.events_table} ("
            "originator_id uuid NOT NULL, "
            "originator_version integer NOT NULL, "
            "topic text, "
            "state bytea, "
            "PRIMARY KEY "
            "(originator_id, originator_version))"
        )
        try:
            c.execute(statement)
        except psycopg2.OperationalError as e:
            raise self.OperationalError(e)

    def insert_events(self, stored_events, **kwargs):
        with self.db.transaction() as c:
            self._insert_events(c, stored_events, **kwargs)

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs,
    ) -> None:
        statement = f"INSERT INTO {self.events_table}" " VALUES (%s, %s, %s, %s)"
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
        try:
            c.executemany(statement, params)
        except psycopg2.IntegrityError as e:
            raise RecordConflictError(e)

    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        statement = "SELECT * " f"FROM {self.events_table} " "WHERE originator_id = %s "
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
        with self.db.transaction() as c:
            c.execute(statement, params)
            for row in c.fetchall():
                stored_events.append(
                    StoredEvent(  # type: ignore
                        originator_id=row["originator_id"],
                        originator_version=row["originator_version"],
                        topic=row["topic"],
                        state=bytes(row["state"]),
                    )
                )
        return stored_events


class PostgresApplicationRecorder(
    PostgresAggregateRecorder,
    ApplicationRecorder,
):
    def _create_table(self, c: cursor):
        super()._create_table(c)
        statement = (
            f"ALTER TABLE {self.events_table} "
            "ADD COLUMN IF NOT EXISTS "
            f"notification_id SERIAL"
        )
        try:
            c.execute(statement)
        except psycopg2.OperationalError as e:
            raise self.OperationalError(e)

        statement = (
            "CREATE UNIQUE INDEX IF NOT EXISTS notification_id_idx "
            f"ON {self.events_table} (notification_id ASC);"
        )
        try:
            c.execute(statement)
        except psycopg2.OperationalError as e:
            raise self.OperationalError(e)

    def select_notifications(self, start: int, limit: int) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """
        statement = (
            "SELECT * "
            f"FROM {self.events_table} "
            "WHERE notification_id>=%s "
            "ORDER BY notification_id "
            "LIMIT %s"
        )
        params = [start, limit]
        with self.db.transaction() as c:
            c.execute(statement, params)
            notifications = []
            for row in c.fetchall():
                notifications.append(
                    Notification(  # type: ignore
                        id=row["notification_id"],
                        originator_id=row["originator_id"],
                        originator_version=row["originator_version"],
                        topic=row["topic"],
                        state=bytes(row["state"]),
                    )
                )
        return notifications

    def max_notification_id(self) -> int:
        """
        Returns the maximum notification ID.
        """
        c = self.db.get_connection().cursor()
        statement = f"SELECT MAX(notification_id) FROM {self.events_table}"
        c.execute(statement)
        return c.fetchone()[0] or 0


class PostgresProcessRecorder(
    PostgresApplicationRecorder,
    ProcessRecorder,
):
    def __init__(
        self, application_name: str, db_name: str, host: str, user: str, password: str
    ):
        super().__init__(application_name, db_name, host, user, password)
        self.tracking_table = self.application_name.lower() + "tracking"

    def _create_table(self, c: cursor):
        super()._create_table(c)
        statement = (
            "CREATE TABLE IF NOT EXISTS "
            f"{self.tracking_table} ("
            "application_name text, "
            "notification_id int, "
            "PRIMARY KEY "
            "(application_name, notification_id))"
        )
        c.execute(statement)

    def max_tracking_id(self, application_name: str) -> int:
        params = [application_name]
        c = self.db.get_connection().cursor()
        statement = (
            "SELECT MAX(notification_id)"
            f"FROM {self.tracking_table} "
            "WHERE application_name=%s"
        )
        c.execute(statement, params)
        return c.fetchone()[0] or 0

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs,
    ) -> None:
        super()._insert_events(c, stored_events, **kwargs)
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            statement = f"INSERT INTO {self.tracking_table} " "VALUES (%s, %s)"
            try:
                c.execute(
                    statement,
                    (
                        tracking.application_name,
                        tracking.notification_id,
                    ),
                )
            except psycopg2.IntegrityError as e:
                raise RecordConflictError(e)


class Factory(InfrastructureFactory):
    DO_CREATE_TABLE = "DO_CREATE_TABLE"
    POSTGRES_DBNAME = "POSTGRES_DBNAME"
    POSTGRES_HOST = "POSTGRES_HOST"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"

    def __init__(self, application_name):
        super().__init__(application_name)
        self.db_name = self.getenv(self.POSTGRES_DBNAME)
        if self.db_name is None:
            raise EnvironmentError(
                "Postgres database name not found "
                "in environment with key "
                f"'{self.POSTGRES_DBNAME}'"
            )

        self.host = self.getenv(self.POSTGRES_HOST)
        if self.host is None:
            raise EnvironmentError(
                "Postgres host not found "
                "in environment with key "
                f"'{self.POSTGRES_HOST}'"
            )

        self.user = self.getenv(self.POSTGRES_USER)
        if self.user is None:
            raise EnvironmentError(
                "Postgres user not found "
                "in environment with key "
                f"'{self.POSTGRES_USER}'"
            )

        self.password = self.getenv(self.POSTGRES_PASSWORD)
        if self.password is None:
            raise EnvironmentError(
                "Postgres password not found "
                "in environment with key "
                f"'{self.POSTGRES_PASSWORD}'"
            )

    def aggregate_recorder(self) -> AggregateRecorder:
        recorder = PostgresAggregateRecorder(
            self.application_name, self.db_name, self.host, self.user, self.password
        )
        if self.do_create_table():
            recorder.create_table()
        return recorder

    def application_recorder(self) -> ApplicationRecorder:
        recorder = PostgresApplicationRecorder(
            self.application_name, self.db_name, self.host, self.user, self.password
        )
        if self.do_create_table():
            recorder.create_table()
        return recorder

    def process_recorder(self) -> ProcessRecorder:
        recorder = PostgresProcessRecorder(
            self.application_name, self.db_name, self.host, self.user, self.password
        )
        if self.do_create_table():
            recorder.create_table()
        return recorder

    def do_create_table(self) -> bool:
        default = "no"
        return bool(strtobool(self.getenv(self.DO_CREATE_TABLE, default) or default))
