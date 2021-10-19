from typing import Any, Generator, List, Mapping, Optional
from uuid import UUID

import asyncpg
from asyncpg import (
    Connection,
    ConnectionDoesNotExistError,
    UniqueViolationError,
)

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    AsyncAggregateRecorder,
    AsyncApplicationRecorder,
    AsyncProcessRecorder,
    InfrastructureFactory,
    IntegrityError,
    InterfaceError,
    Notification,
    ProcessRecorder,
    StoredEvent,
    Tracking,
)
from eventsourcing.utils import async_retry, strtobool


class AsyncPostgresDatastore:
    def __init__(
        self,
        dbname: str,
        host: str,
        port: str,
        user: str,
        password: str,
        lock_timeout: int = 0,
        idle_in_transaction_session_timeout: int = 0,
    ):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.lock_timeout = lock_timeout
        self.idle_in_transaction_session_timeout = idle_in_transaction_session_timeout

        self.pool = asyncpg.create_pool(
            database=self.dbname,
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            min_size=1,
        )

    def __await__(self) -> Generator[Any, None, "AsyncPostgresDatastore"]:
        try:
            yield from self.pool.__await__()
        except OSError as e:
            raise InterfaceError(e)
        return self

    async def close(self) -> None:
        await self.pool.close()


class AsyncPostgresAggregateRecorder(AsyncAggregateRecorder):
    def __init__(self, datastore: AsyncPostgresDatastore, events_table_name: str):
        self.datastore = datastore
        self.events_table_name = events_table_name
        self.create_table_statements = self.construct_create_table_statements()
        self.create_function_statements = self.construct_create_function_statements()
        # self.insert_events_statement = (
        #     f"INSERT INTO {self.events_table_name} VALUES ($1, $2, $3, $4)"
        # )
        self.insert_events_statement = (
            f"SELECT insert_{self.events_table_name}($1::uuid[], $2::integer[], "
            f"$3::text[], $4::bytea[])"
        )
        self.select_events_statement = (
            f"SELECT * FROM {self.events_table_name} WHERE originator_id = $1"
        )
        self.lock_statements = [
            f"SET LOCAL lock_timeout = '{self.datastore.lock_timeout}s'",
            f"LOCK TABLE {self.events_table_name} IN EXCLUSIVE MODE",
        ]

    def construct_create_table_statements(self) -> List[str]:
        create_events_table = (
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
        return [create_events_table]

    def construct_create_function_statements(self) -> List[str]:
        create_insert_events_function = f"""
CREATE OR REPLACE FUNCTION insert_{self.events_table_name}(
    originator_ids uuid[],
    originator_versions integer[],
    topics text[],
    states bytea[]
    )
RETURNS VOID
LANGUAGE plpgsql AS
$$
DECLARE
    number_ids integer := array_length(originator_ids, 1);
begin
    SET LOCAL lock_timeout = '{self.datastore.lock_timeout}s';
    LOCK TABLE {self.events_table_name} IN EXCLUSIVE MODE;

    FOR index IN 1..number_ids
    LOOP
        INSERT INTO {self.events_table_name} VALUES (
            originator_ids[index],
            originator_versions[index],
            topics[index],
            states[index]
        );
    END LOOP;
end;
$$;
"""
        return [create_insert_events_function]

    def __await__(self) -> Generator[Any, None, "AsyncPostgresAggregateRecorder"]:
        yield from self.create_table().__await__()
        return self

    async def create_table(self) -> None:
        async with self.datastore.pool.acquire() as connection:
            await self._set_idle_in_transaction_session_timeout(connection)
            async with connection.transaction():
                for statement in self.create_table_statements:
                    await connection.fetch(statement)
                for statement in self.create_function_statements:
                    await connection.fetch(statement)

    async def _set_idle_in_transaction_session_timeout(
        self, connection: Connection
    ) -> None:
        await connection.execute(
            f"SET idle_in_transaction_session_timeout = "
            f"'{self.datastore.idle_in_transaction_session_timeout}s'"
        )

    @async_retry(ConnectionDoesNotExistError, max_attempts=2)
    async def async_insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> None:
        try:
            async with self.datastore.pool.acquire() as connection:
                await self._set_idle_in_transaction_session_timeout(connection)
                async with connection.transaction():
                    await self._async_insert_events(connection, stored_events, **kwargs)
        except UniqueViolationError as e:
            raise IntegrityError(e)

    async def _async_insert_events(
        self, connection: Connection, stored_events: List[StoredEvent], **kwargs: Any
    ) -> None:
        if len(stored_events):
            originator_ids = []
            originator_versions = []
            topics = []
            states = []
            for stored_event in stored_events:
                originator_ids.append(stored_event.originator_id)
                originator_versions.append(stored_event.originator_version)
                topics.append(stored_event.topic)
                states.append(stored_event.state)

            await connection.execute(
                self.insert_events_statement,
                originator_ids,
                originator_versions,
                topics,
                states,
            )

    @async_retry(ConnectionDoesNotExistError, max_attempts=2)
    async def async_select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        stored_events = []

        parts = [self.select_events_statement]
        params: List[Any] = [originator_id]
        if gt is not None:
            params.append(gt)
            parts.append(f"AND originator_version > ${len(params)}")
        if lte is not None:
            params.append(lte)
            parts.append(f"AND originator_version <= ${len(params)}")
        parts.append("ORDER BY originator_version")
        if desc is False:
            parts.append("ASC")
        else:
            parts.append("DESC")
        if limit is not None:
            params.append(limit)
            parts.append(f"LIMIT ${len(params)}")
        statement = " ".join(parts)

        async with self.datastore.pool.acquire() as connection:
            for record in await connection.fetch(statement, *params):
                stored_events.append(
                    StoredEvent(
                        originator_id=record["originator_id"],
                        originator_version=record["originator_version"],
                        state=record["state"],
                        topic=record["topic"],
                    )
                )
        return stored_events


class AsyncPostgresApplicationRecorder(
    AsyncPostgresAggregateRecorder,
    AsyncApplicationRecorder,
):
    def __init__(
        self,
        datastore: AsyncPostgresDatastore,
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
        self.max_notification_id_statement = (
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
            "notification_id BIGSERIAL, "
            "PRIMARY KEY "
            "(originator_id, originator_version)) "
            "WITH (autovacuum_enabled=false)",
            f"CREATE UNIQUE INDEX IF NOT EXISTS "
            f"{self.events_table_name}_notification_id_idx "
            f"ON {self.events_table_name} (notification_id ASC);",
        ]
        return statements

    async def async_select_notifications(
        self, start: int, limit: int
    ) -> List[Notification]:
        notifications = []
        async with self.datastore.pool.acquire() as connection:
            for record in await connection.fetch(
                self.select_notifications_statement, start, limit
            ):
                notifications.append(
                    Notification(
                        id=record["notification_id"],
                        originator_id=record["originator_id"],
                        originator_version=record["originator_version"],
                        topic=record["topic"],
                        state=bytes(record["state"]),
                    )
                )
        return notifications

    async def async_max_notification_id(self) -> int:
        async with self.datastore.pool.acquire() as connection:
            return await connection.fetchval(self.max_notification_id_statement) or 0


class AsyncPostgresProcessRecorder(
    AsyncPostgresApplicationRecorder,
    AsyncProcessRecorder,
):
    def __init__(
        self,
        datastore: AsyncPostgresDatastore,
        events_table_name: str,
        tracking_table_name: str,
    ):
        self.tracking_table_name = tracking_table_name
        super().__init__(datastore, events_table_name)
        self.insert_tracking_statement = (
            f"INSERT INTO {self.tracking_table_name} VALUES ($1, $2)"
        )
        self.max_tracking_id_statement = (
            "SELECT MAX(notification_id) "
            f"FROM {self.tracking_table_name} "
            "WHERE application_name=$1"
        )

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

    async def _async_insert_events(
        self, connection: Connection, stored_events: List[StoredEvent], **kwargs: Any
    ) -> None:
        await super()._async_insert_events(connection, stored_events, **kwargs)
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            await connection.execute(
                self.insert_tracking_statement,
                tracking.application_name,
                tracking.notification_id,
            )

    async def async_max_tracking_id(self, application_name: str) -> int:
        async with self.datastore.pool.acquire() as connection:
            await self._set_idle_in_transaction_session_timeout(connection)
            async with connection.transaction():
                return (
                    await connection.fetchval(
                        self.max_tracking_id_statement, application_name
                    )
                    or 0
                )


class Factory(InfrastructureFactory):
    POSTGRES_DBNAME = "POSTGRES_DBNAME"
    POSTGRES_HOST = "POSTGRES_HOST"
    POSTGRES_PORT = "POSTGRES_PORT"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"
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

        self.datastore = AsyncPostgresDatastore(
            dbname=dbname,
            host=host,
            port=port,
            user=user,
            password=password,
            lock_timeout=lock_timeout,
            idle_in_transaction_session_timeout=idle_in_transaction_session_timeout,
        )
        self._requires_await.append(self.datastore)

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        prefix = self.application_name.lower() or "stored"
        events_table_name = prefix + "_" + purpose
        recorder = AsyncPostgresAggregateRecorder(
            datastore=self.datastore, events_table_name=events_table_name
        )
        self._requires_await.append(recorder)
        return recorder

    def application_recorder(self) -> ApplicationRecorder:
        prefix = self.application_name.lower() or "stored"
        events_table_name = prefix + "_events"
        recorder = AsyncPostgresApplicationRecorder(
            datastore=self.datastore, events_table_name=events_table_name
        )
        self._requires_await.append(recorder)
        return recorder

    def process_recorder(self) -> ProcessRecorder:
        prefix = self.application_name.lower() or "stored"
        events_table_name = prefix + "_events"
        prefix = self.application_name.lower() or "notification"
        tracking_table_name = prefix + "_tracking"
        recorder = AsyncPostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            tracking_table_name=tracking_table_name,
        )
        self._requires_await.append(recorder)
        return recorder

    def env_create_table(self) -> bool:
        default = "yes"
        return bool(strtobool(self.getenv(self.CREATE_TABLE) or default))

    async def async_close(self) -> None:
        await self.datastore.close()
