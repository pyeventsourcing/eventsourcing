import threading
from distutils.util import strtobool
from typing import Any, List, Optional
from uuid import UUID

import psycopg2
import psycopg2.extras
import psycopg2.errors
from psycopg2.errorcodes import DUPLICATE_TABLE, UNDEFINED_TABLE
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
    def __init__(self, datastore: PostgresDatastore, events_table_name: str):
        self.datastore = datastore
        self.events_table_name = events_table_name

    def create_table(self) -> None:
        with self.datastore.transaction() as c:
            try:
                self._createtable(c)
            except psycopg2.Error as e:
                raise OperationalError(e)

    def _createtable(self, c: cursor) -> None:
        statement = (
            "CREATE TABLE "
            f"{self.events_table_name} ("
            "originator_id uuid NOT NULL, "
            "originator_version integer NOT NULL, "
            "topic text, "
            "state bytea, "
            "PRIMARY KEY "
            "(originator_id, originator_version))"
        )
        c.execute(statement)

    def insert_events(self, stored_events: List[StoredEvent], **kwargs):
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
        **kwargs,
    ) -> None:
        statement = f"INSERT INTO {self.events_table_name}" " VALUES (%s, %s, %s, %s)"
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
        c.executemany(statement, params)

    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        statement = (
            "SELECT * " f"FROM {self.events_table_name} " "WHERE originator_id = %s "
        )
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


class PostgresApplicationRecorder(
    PostgresAggregateRecorder,
    ApplicationRecorder,
):
    def _createtable(self, c: cursor) -> None:
        super()._createtable(c)
        statement = (
            f"ALTER TABLE {self.events_table_name} "
            "ADD COLUMN "
            f"notification_id SERIAL"
        )
        c.execute(statement)

        statement = (
            f"CREATE UNIQUE INDEX {self.events_table_name}_notification_id_idx "
            f"ON {self.events_table_name} (notification_id ASC);"
        )
        c.execute(statement)

    def select_notifications(self, start: int, limit: int) -> List[Notification]:
        """
        Returns a list of event notifications
        from 'start', limited by 'limit'.
        """
        statement = (
            "SELECT * "
            f"FROM {self.events_table_name} "
            "WHERE notification_id>=%s "
            "ORDER BY notification_id "
            "LIMIT %s"
        )
        params = [start, limit]
        try:
            with self.datastore.transaction() as c:
                c.execute(statement, params)
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
        statement = f"SELECT MAX(notification_id) FROM {self.events_table_name}"
        try:
            c = self.datastore.get_connection().cursor()
            c.execute(statement)
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
        super().__init__(datastore, events_table_name)
        self.tracking_table_name = tracking_table_name

    def _createtable(self, c: cursor) -> None:
        super()._createtable(c)
        statement = (
            "CREATE TABLE "
            f"{self.tracking_table_name} ("
            "application_name text, "
            "notification_id int, "
            "PRIMARY KEY "
            "(application_name, notification_id))"
        )
        c.execute(statement)

    def max_tracking_id(self, application_name: str) -> int:
        params = [application_name]
        statement = (
            "SELECT MAX(notification_id)"
            f"FROM {self.tracking_table_name} "
            "WHERE application_name=%s"
        )
        try:
            c = self.datastore.get_connection().cursor()
            c.execute(statement, params)
            return c.fetchone()[0] or 0
        except psycopg2.Error as e:
            raise OperationalError(e)

    def _insert_events(
        self,
        c: cursor,
        stored_events: List[StoredEvent],
        **kwargs,
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
    DO_CREATE_TABLE = "DO_CREATE_TABLE"
    POSTGRES_DBNAME = "POSTGRES_DBNAME"
    POSTGRES_HOST = "POSTGRES_HOST"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"

    def __init__(self, application_name):
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
            user=user,
            password=password,
        )

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        prefix = self.application_name or "stored"
        events_table_name = prefix + "_" + purpose
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name=events_table_name
        )
        if self.do_createtable():
            recorder.create_table()
        return recorder

    def application_recorder(self) -> ApplicationRecorder:
        prefix = self.application_name or "stored"
        events_table_name = prefix + "_events"
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name=events_table_name
        )
        if self.do_createtable():
            recorder.create_table()
        return recorder

    def process_recorder(self) -> ProcessRecorder:
        prefix = self.application_name or "stored"
        events_table_name = prefix + "_events"
        prefix = self.application_name or "notification"
        tracking_table_name = prefix + "_tracking"
        recorder = PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            tracking_table_name=tracking_table_name,
        )
        if self.do_createtable():
            recorder.create_table()
        return recorder

    def do_createtable(self) -> bool:
        default = "no"
        return bool(strtobool(self.getenv(self.DO_CREATE_TABLE, default) or default))
