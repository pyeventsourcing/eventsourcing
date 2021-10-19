import os
from unittest import skip
from uuid import uuid4

from asyncpg import UndefinedFunctionError, UndefinedTableError

from eventsourcing.async_postgres import (
    AsyncPostgresAggregateRecorder,
    AsyncPostgresApplicationRecorder,
    AsyncPostgresDatastore,
    AsyncPostgresProcessRecorder,
    Factory,
)
from eventsourcing.persistence import (
    AsyncProcessRecorder,
    InfrastructureFactory,
    InterfaceError,
    StoredEvent,
)
from eventsourcing.tests.async_aggregaterecorder_testcase import (
    AsyncAggregateRecorderTestCase,
)
from eventsourcing.tests.async_applicationrecorder_testcase import (
    AsyncApplicationRecorderTestCase,
)
from eventsourcing.tests.async_processrecorder_testcase import (
    AsyncProcessRecorderTestCase,
)
from eventsourcing.tests.asyncio_testcase import IsolatedAsyncioTestCase
from eventsourcing.tests.infrastructure_testcases import (
    InfrastructureFactoryTestCase,
)
from eventsourcing.tests.test_postgres import pg_close_all_connections
from eventsourcing.utils import get_topic


class TestAsyncPostgresDatastore(IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        await self.datastore.pool.close()
        pg_close_all_connections()

    async def test_connection_and_transaction(self):
        self.datastore = await AsyncPostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        async with self.datastore.pool.acquire() as connection:
            # Open a transaction.
            async with connection.transaction():
                # Run the query passing the request argument.
                result = await connection.fetchval("select 2 ^ $1", 4)
                self.assertEqual(result, 16)

    async def test_connect_failure_raises_interface_error(self):
        self.datastore = AsyncPostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="54321",
            user="eventsourcing",
            password="eventsourcing",
        )
        with self.assertRaises(InterfaceError):
            await self.datastore


class TestAsyncPostgresAggregateRecorder(AsyncAggregateRecorderTestCase):
    async def asyncSetUp(self) -> None:
        self.datastore = await AsyncPostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        await drop_postgres_function(self.datastore, "insert_events")
        await drop_postgres_table(self.datastore, "stored_events")

    async def asyncTearDown(self) -> None:
        await drop_postgres_function(self.datastore, "insert_events")
        await drop_postgres_table(self.datastore, "stored_events")
        await self.datastore.pool.close()
        pg_close_all_connections()

    async def create_recorder(self) -> AsyncPostgresAggregateRecorder:
        recorder = AsyncPostgresAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        await recorder.create_table()
        return recorder

    async def test_performance(self):
        await super().test_performance()

    async def test_performance_concurrent(self):
        await super().test_performance_concurrent()

    async def test_insert_and_select(self):
        await super().test_insert_and_select()

    async def test_retry_insert_events_after_closing_connection(self):
        # Construct the recorder.
        recorder = await self.create_recorder()

        # Write a stored event.
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        await recorder.async_insert_events([stored_event1])

        # Close connections.
        pg_close_all_connections()

        # Write a stored event.
        stored_event2 = StoredEvent(
            originator_id=uuid4(),
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        await recorder.async_insert_events([stored_event2])

    async def test_retry_select_events_after_closing_connection(self):
        # Construct the recorder.
        recorder = await self.create_recorder()

        # Write a stored event.
        originator_id = uuid4()
        stored_event1 = StoredEvent(
            originator_id=originator_id,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        await recorder.async_insert_events([stored_event1])

        # Close connections.
        pg_close_all_connections()

        # Select events.
        await recorder.async_select_events(originator_id)


# class TestAsyncPostgresAggregateRecorderErrors(TestCase):
#     def setUp(self) -> None:
#         self.datastore = PostgresDatastore(
#             "eventsourcing",
#             "127.0.0.1",
#             "5432",
#             "eventsourcing",
#             "eventsourcing",
#         )
#         self.drop_tables()
#
#     def tearDown(self) -> None:
#         self.drop_tables()
#
#     def drop_tables(self):
#         drop_postgres_table(self.datastore, "stored_events")
#
#     def create_recorder(self):
#         return PostgresAggregateRecorder(
#             datastore=self.datastore, events_table_name="stored_events"
#         )
#
#     def test_create_table_raises_programming_error_when_sql_is_broken(self):
#         recorder = self.create_recorder()
#
#         # Mess up the statement.
#         recorder.create_table_statements = ["BLAH"]
#         with self.assertRaises(ProgrammingError):
#             recorder.create_table()
#
#     def test_insert_events_raises_programming_error_when_table_not_created(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Write a stored event without creating the table.
#         stored_event1 = StoredEvent(
#             originator_id=uuid4(),
#             originator_version=0,
#             topic="topic1",
#             state=b"state1",
#         )
#         with self.assertRaises(ProgrammingError):
#             recorder.insert_events([stored_event1])
#
#     def test_insert_events_raises_programming_error_when_sql_is_broken(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Create the table.
#         recorder.create_table()
#
#         # Write a stored event with broken statement.
#         recorder.insert_events_statement = "BLAH"
#         stored_event1 = StoredEvent(
#             originator_id=uuid4(),
#             originator_version=0,
#             topic="topic1",
#             state=b"state1",
#         )
#         with self.assertRaises(ProgrammingError):
#             recorder.insert_events([stored_event1])
#
#     def test_select_events_raises_programming_error_when_table_not_created(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Select events without creating the table.
#         originator_id = uuid4()
#         with self.assertRaises(ProgrammingError):
#             recorder.select_events(originator_id=originator_id)
#
#     def test_select_events_raises_programming_error_when_sql_is_broken(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Create the table.
#         recorder.create_table()
#
#         # Select events with broken statement.
#         recorder.select_events_statement = "BLAH"
#         originator_id = uuid4()
#         with self.assertRaises(ProgrammingError):
#             recorder.select_events(originator_id=originator_id)
#
#     def test_duplicate_prepared_statement_error_is_ignored(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Create the table.
#         recorder.create_table()
#
#         # Check the statement is not prepared.
#         statement_name = "select_stored_events"
#         conn = self.datastore.get_connection()
#         self.assertFalse(conn.is_prepared.get(statement_name))
#
#         # Cause the statement to be prepared.
#         recorder.select_events(originator_id=uuid4())
#
#         # Check the statement was prepared.
#         conn = self.datastore.get_connection()
#         self.assertTrue(conn.is_prepared.get(statement_name))
#
#         # Forget the statement is prepared.
#         del conn.is_prepared[statement_name]
#
#         # Should ignore "duplicate prepared statement" error.
#         recorder.select_events(originator_id=uuid4())
#
#         # Check the statement was prepared.
#         conn = self.datastore.get_connection()
#         self.assertTrue(conn.is_prepared.get(statement_name))
#
#


class TestAsyncPostgresApplicationRecorder(AsyncApplicationRecorderTestCase):
    async def asyncSetUp(self) -> None:
        self.datastore = await AsyncPostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        await drop_postgres_table(self.datastore, "stored_events")

    async def asyncTearDown(self) -> None:
        await drop_postgres_table(self.datastore, "stored_events")
        await self.datastore.pool.close()
        pg_close_all_connections()

    async def create_recorder(self):
        recorder = AsyncPostgresApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        await recorder.create_table()
        return recorder

    async def test_insert_select(self):
        await super().test_insert_select()

    @skip
    def test_concurrent_no_conflicts(self):
        super().test_concurrent_no_conflicts()

    @skip
    def test_concurrent_throughput(self):
        super().test_concurrent_throughput()


#     def test_retry_select_notifications_after_closing_connection(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Check we have a connection (from create_table).
#         self.assertTrue(self.datastore._connections)
#
#         # Write a stored event.
#         originator_id = uuid4()
#         stored_event1 = StoredEvent(
#             originator_id=originator_id,
#             originator_version=0,
#             topic="topic1",
#             state=b"state1",
#         )
#         recorder.insert_events([stored_event1])
#
#         # Close connections.
#         pg_close_all_connections()
#
#         # Select events.
#         recorder.select_notifications(start=1, limit=1)
#
#     def test_retry_max_notification_id_after_closing_connection(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Check we have a connection (from create_table).
#         self.assertTrue(self.datastore._connections)
#
#         # Write a stored event.
#         originator_id = uuid4()
#         stored_event1 = StoredEvent(
#             originator_id=originator_id,
#             originator_version=0,
#             topic="topic1",
#             state=b"state1",
#         )
#         recorder.insert_events([stored_event1])
#
#         # Close connections.
#         pg_close_all_connections()
#
#         # Select events.
#         recorder.max_notification_id()
#
#
# class TestPostgresApplicationRecorderErrors(TestCase):
#     def setUp(self) -> None:
#         self.datastore = PostgresDatastore(
#             "eventsourcing",
#             "127.0.0.1",
#             "5432",
#             "eventsourcing",
#             "eventsourcing",
#         )
#         self.drop_tables()
#
#     def tearDown(self) -> None:
#         self.drop_tables()
#
#     def drop_tables(self):
#         drop_postgres_table(self.datastore, "stored_events")
#
#     def create_recorder(self):
#         return PostgresApplicationRecorder(
#             self.datastore, events_table_name="stored_events"
#         )
#
#     def test_select_notification_raises_programming_error_when_table_not_created(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Select notifications without creating table.
#         with self.assertRaises(ProgrammingError):
#             recorder.select_notifications(start=1, limit=1)
#
#     def test_select_notification_raises_programming_error_when_sql_is_broken(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Create table.
#         recorder.create_table()
#
#         # Select notifications with broken statement.
#         recorder.select_notifications_statement = "BLAH"
#         with self.assertRaises(ProgrammingError):
#             recorder.select_notifications(start=1, limit=1)
#
#     def test_max_notification_id_raises_programming_error_when_table_not_created(self):
#         # Construct the recorder.
#         recorder = PostgresApplicationRecorder(
#             datastore=self.datastore, events_table_name="stored_events"
#         )
#
#         # Select notifications without creating table.
#         with self.assertRaises(ProgrammingError):
#             recorder.max_notification_id()
#
#     def test_max_notification_id_raises_programming_error_when_sql_is_broken(self):
#         # Construct the recorder.
#         recorder = PostgresApplicationRecorder(
#             datastore=self.datastore, events_table_name="stored_events"
#         )
#
#         # Create table.
#         recorder.create_table()
#
#         # Select notifications with broken statement.
#         recorder.max_notification_id_statement = "BLAH"
#         with self.assertRaises(ProgrammingError):
#             recorder.max_notification_id()
#
#
class TestAsyncPostgresProcessRecorder(AsyncProcessRecorderTestCase):
    async def asyncSetUp(self) -> None:
        self.datastore = await AsyncPostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        await drop_postgres_table(self.datastore, "stored_events")
        await drop_postgres_table(self.datastore, "notification_tracking")

    async def asyncTearDown(self) -> None:
        await drop_postgres_table(self.datastore, "stored_events")
        await drop_postgres_table(self.datastore, "notification_tracking")
        await self.datastore.pool.close()
        pg_close_all_connections()

    async def create_recorder(self) -> AsyncProcessRecorder:
        recorder = AsyncPostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
            tracking_table_name="notification_tracking",
        )
        await recorder.create_table()
        return recorder

    async def test_insert_select(self):
        await super().test_insert_select()

    async def test_performance(self):
        await super().test_performance()


#     def test_retry_max_tracking_id_after_closing_connection(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Check we have a connection (from create_table).
#         self.assertTrue(self.datastore._connections)
#
#         # Write a stored event.
#         originator_id = uuid4()
#         stored_event1 = StoredEvent(
#             originator_id=originator_id,
#             originator_version=0,
#             topic="topic1",
#             state=b"state1",
#         )
#         recorder.insert_events([stored_event1], tracking=Tracking("upstream", 1))
#
#         # Close connections.
#         pg_close_all_connections()
#
#         # Select events.
#         notification_id = recorder.max_tracking_id("upstream")
#         self.assertEqual(notification_id, 1)
#
#
# class TestPostgresProcessRecorderErrors(TestCase):
#     def setUp(self) -> None:
#         self.datastore = PostgresDatastore(
#             "eventsourcing",
#             "127.0.0.1",
#             "5432",
#             "eventsourcing",
#             "eventsourcing",
#         )
#         self.drop_tables()
#
#     def tearDown(self) -> None:
#         self.drop_tables()
#
#     def drop_tables(self):
#         drop_postgres_table(self.datastore, "stored_events")
#         drop_postgres_table(self.datastore, "notification_tracking")
#
#     def create_recorder(self):
#         return PostgresProcessRecorder(
#             datastore=self.datastore,
#             events_table_name="stored_events",
#             tracking_table_name="notification_tracking",
#         )
#
#     def test_max_tracking_id_raises_programming_error_when_table_not_created(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Get max tracking ID without creating table.
#         with self.assertRaises(ProgrammingError):
#             recorder.max_tracking_id("upstream")
#
#     def test_max_tracking_id_raises_programming_error_when_sql_is_broken(self):
#         # Construct the recorder.
#         recorder = self.create_recorder()
#
#         # Create table.
#         recorder.create_table()
#
#         # Mess up the SQL statement.
#         recorder.max_tracking_id_statement = "BLAH"
#
#         # Get max tracking ID with broken statement.
#         with self.assertRaises(ProgrammingError):
#             recorder.max_tracking_id("upstream")
#
#
# class TestPostgresInfrastructureFactory(InfrastructureFactoryTestCase):
#     def test_create_application_recorder(self):
#         super().test_create_application_recorder()
#
#     def expected_factory_class(self):
#         return Factory
#
#     def expected_aggregate_recorder_class(self):
#         return PostgresAggregateRecorder
#
#     def expected_application_recorder_class(self):
#         return PostgresApplicationRecorder
#
#     def expected_process_recorder_class(self):
#         return PostgresProcessRecorder
#
#     def setUp(self) -> None:
#         os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
#         os.environ[Factory.POSTGRES_DBNAME] = "eventsourcing"
#         os.environ[Factory.POSTGRES_HOST] = "127.0.0.1"
#         os.environ[Factory.POSTGRES_PORT] = "5432"
#         os.environ[Factory.POSTGRES_USER] = "eventsourcing"
#         os.environ[Factory.POSTGRES_PASSWORD] = "eventsourcing"
#         if Factory.POSTGRES_CONN_MAX_AGE in os.environ:
#             del os.environ[Factory.POSTGRES_CONN_MAX_AGE]
#         if Factory.POSTGRES_PRE_PING in os.environ:
#             del os.environ[Factory.POSTGRES_PRE_PING]
#         if Factory.POSTGRES_LOCK_TIMEOUT in os.environ:
#             del os.environ[Factory.POSTGRES_LOCK_TIMEOUT]
#         if Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT in os.environ:
#             del os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT]
#         self.drop_tables()
#         super().setUp()
#
#     def tearDown(self) -> None:
#         self.drop_tables()
#         if Factory.POSTGRES_DBNAME in os.environ:
#             del os.environ[Factory.POSTGRES_DBNAME]
#         if Factory.POSTGRES_HOST in os.environ:
#             del os.environ[Factory.POSTGRES_HOST]
#         if Factory.POSTGRES_PORT in os.environ:
#             del os.environ[Factory.POSTGRES_PORT]
#         if Factory.POSTGRES_USER in os.environ:
#             del os.environ[Factory.POSTGRES_USER]
#         if Factory.POSTGRES_PASSWORD in os.environ:
#             del os.environ[Factory.POSTGRES_PASSWORD]
#         if Factory.POSTGRES_CONN_MAX_AGE in os.environ:
#             del os.environ[Factory.POSTGRES_CONN_MAX_AGE]
#         if Factory.POSTGRES_PRE_PING in os.environ:
#             del os.environ[Factory.POSTGRES_PRE_PING]
#         if Factory.POSTGRES_LOCK_TIMEOUT in os.environ:
#             del os.environ[Factory.POSTGRES_LOCK_TIMEOUT]
#         if Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT in os.environ:
#             del os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT]
#         super().tearDown()
#
#     def drop_tables(self):
#         datastore = PostgresDatastore(
#             "eventsourcing",
#             "127.0.0.1",
#             "5432",
#             "eventsourcing",
#             "eventsourcing",
#         )
#         drop_postgres_table(datastore, "testcase_events")
#         drop_postgres_table(datastore, "testcase_tracking")
#
#     def test_conn_max_age_is_set_to_empty_string(self):
#         os.environ[Factory.POSTGRES_CONN_MAX_AGE] = ""
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.conn_max_age, None)
#
#     def test_conn_max_age_is_set_to_number(self):
#         os.environ[Factory.POSTGRES_CONN_MAX_AGE] = "0"
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.conn_max_age, 0)
#
#     def test_lock_timeout_is_zero_by_default(self):
#         self.assertTrue(Factory.POSTGRES_LOCK_TIMEOUT not in os.environ)
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.lock_timeout, 0)
#
#         os.environ[Factory.POSTGRES_LOCK_TIMEOUT] = ""
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.lock_timeout, 0)
#
#     def test_lock_timeout_is_nonzero(self):
#         os.environ[Factory.POSTGRES_LOCK_TIMEOUT] = "1"
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.lock_timeout, 1)
#
#     def test_idle_in_transaction_session_timeout_is_zero_by_default(self):
#         self.assertTrue(
#             Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT not in os.environ
#         )
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.idle_in_transaction_session_timeout, 0)
#
#         os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = ""
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.idle_in_transaction_session_timeout, 0)
#
#     def test_idle_in_transaction_session_timeout_is_nonzero(self):
#         os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = "1"
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.idle_in_transaction_session_timeout, 1)
#
#     def test_pre_ping_off_by_default(self):
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.pre_ping, False)
#
#     def test_pre_ping_off(self):
#         os.environ[Factory.POSTGRES_PRE_PING] = "off"
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.pre_ping, False)
#
#     def test_pre_ping_on(self):
#         os.environ[Factory.POSTGRES_PRE_PING] = "on"
#         self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(self.factory.datastore.pre_ping, True)
#
#     def test_environment_error_raised_when_conn_max_age_not_a_float(self):
#         os.environ[Factory.POSTGRES_CONN_MAX_AGE] = "abc"
#         with self.assertRaises(EnvironmentError) as cm:
#             self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(
#             cm.exception.args[0],
#             "Postgres environment value for key 'POSTGRES_CONN_MAX_AGE' "
#             "is invalid. If set, a float or empty string is expected: 'abc'",
#         )
#
#     def test_environment_error_raised_when_lock_timeout_not_an_integer(self):
#         os.environ[Factory.POSTGRES_LOCK_TIMEOUT] = "abc"
#         with self.assertRaises(EnvironmentError) as cm:
#             self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(
#             cm.exception.args[0],
#             "Postgres environment value for key 'POSTGRES_LOCK_TIMEOUT' "
#             "is invalid. If set, an integer or empty string is expected: 'abc'",
#         )
#
#     def test_environment_error_raised_when_idle_in_transaction_session_timeout_not_an_integer(
#         self,
#     ):
#         os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = "abc"
#         with self.assertRaises(EnvironmentError) as cm:
#             self.factory = Factory("TestCase", os.environ)
#         self.assertEqual(
#             cm.exception.args[0],
#             "Postgres environment value for key "
#             "'POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT' "
#             "is invalid. If set, an integer or empty string is expected: 'abc'",
#         )
#
#     def test_environment_error_raised_when_dbname_missing(self):
#         del os.environ[Factory.POSTGRES_DBNAME]
#         with self.assertRaises(EnvironmentError) as cm:
#             self.factory = InfrastructureFactory.construct("TestCase")
#         self.assertEqual(
#             cm.exception.args[0],
#             "Postgres database name not found in environment "
#             "with key 'POSTGRES_DBNAME'",
#         )
#
#     def test_environment_error_raised_when_dbhost_missing(self):
#         del os.environ[Factory.POSTGRES_HOST]
#         with self.assertRaises(EnvironmentError) as cm:
#             self.factory = InfrastructureFactory.construct("TestCase")
#         self.assertEqual(
#             cm.exception.args[0],
#             "Postgres host not found in environment with key 'POSTGRES_HOST'",
#         )
#
#     def test_environment_error_raised_when_user_missing(self):
#         del os.environ[Factory.POSTGRES_USER]
#         with self.assertRaises(EnvironmentError) as cm:
#             self.factory = InfrastructureFactory.construct("TestCase")
#         self.assertEqual(
#             cm.exception.args[0],
#             "Postgres user not found in environment with key 'POSTGRES_USER'",
#         )
#
#     def test_environment_error_raised_when_password_missing(self):
#         del os.environ[Factory.POSTGRES_PASSWORD]
#         with self.assertRaises(EnvironmentError) as cm:
#             self.factory = InfrastructureFactory.construct("TestCase")
#         self.assertEqual(
#             cm.exception.args[0],
#             "Postgres password not found in environment with key 'POSTGRES_PASSWORD'",
#         )


class TestAsyncPostgresInfrastructureFactory(
    IsolatedAsyncioTestCase, InfrastructureFactoryTestCase
):
    def test_create_application_recorder(self):
        super().test_create_application_recorder()

    def expected_factory_class(self):
        return Factory

    def expected_aggregate_recorder_class(self):
        return AsyncPostgresAggregateRecorder

    def expected_application_recorder_class(self):
        return AsyncPostgresApplicationRecorder

    def expected_process_recorder_class(self):
        return AsyncPostgresProcessRecorder

    def setUp(self) -> None:
        os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
        os.environ[Factory.POSTGRES_DBNAME] = "eventsourcing"
        os.environ[Factory.POSTGRES_HOST] = "127.0.0.1"
        os.environ[Factory.POSTGRES_PORT] = "5432"
        os.environ[Factory.POSTGRES_USER] = "eventsourcing"
        os.environ[Factory.POSTGRES_PASSWORD] = "eventsourcing"
        if Factory.POSTGRES_LOCK_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_LOCK_TIMEOUT]
        if Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT]
        super().setUp()

    def tearDown(self) -> None:
        if Factory.POSTGRES_DBNAME in os.environ:
            del os.environ[Factory.POSTGRES_DBNAME]
        if Factory.POSTGRES_HOST in os.environ:
            del os.environ[Factory.POSTGRES_HOST]
        if Factory.POSTGRES_PORT in os.environ:
            del os.environ[Factory.POSTGRES_PORT]
        if Factory.POSTGRES_USER in os.environ:
            del os.environ[Factory.POSTGRES_USER]
        if Factory.POSTGRES_PASSWORD in os.environ:
            del os.environ[Factory.POSTGRES_PASSWORD]
        if Factory.POSTGRES_LOCK_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_LOCK_TIMEOUT]
        if Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT]
        super().tearDown()
        pg_close_all_connections()

    def test_lock_timeout_is_zero_by_default(self):
        self.assertTrue(Factory.POSTGRES_LOCK_TIMEOUT not in os.environ)
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.lock_timeout, 0)

        os.environ[Factory.POSTGRES_LOCK_TIMEOUT] = ""
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.lock_timeout, 0)

    def test_lock_timeout_is_nonzero(self):
        os.environ[Factory.POSTGRES_LOCK_TIMEOUT] = "1"
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.lock_timeout, 1)

    def test_idle_in_transaction_session_timeout_is_zero_by_default(self):
        self.assertTrue(
            Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT not in os.environ
        )
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.idle_in_transaction_session_timeout, 0)

        os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = ""
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.idle_in_transaction_session_timeout, 0)

    def test_idle_in_transaction_session_timeout_is_nonzero(self):
        os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = "1"
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.idle_in_transaction_session_timeout, 1)

    def test_environment_error_raised_when_lock_timeout_not_an_integer(self):
        os.environ[Factory.POSTGRES_LOCK_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory("TestCase", os.environ)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_LOCK_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_idle_in_transaction_session_timeout_not_an_integer(
        self,
    ):
        os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory("TestCase", os.environ)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key "
            "'POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_dbname_missing(self):
        del os.environ[Factory.POSTGRES_DBNAME]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct("TestCase")
        self.assertEqual(
            cm.exception.args[0],
            "Postgres database name not found in environment "
            "with key 'POSTGRES_DBNAME'",
        )

    def test_environment_error_raised_when_dbhost_missing(self):
        del os.environ[Factory.POSTGRES_HOST]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct("TestCase")
        self.assertEqual(
            cm.exception.args[0],
            "Postgres host not found in environment with key 'POSTGRES_HOST'",
        )

    def test_environment_error_raised_when_user_missing(self):
        del os.environ[Factory.POSTGRES_USER]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct("TestCase")
        self.assertEqual(
            cm.exception.args[0],
            "Postgres user not found in environment with key 'POSTGRES_USER'",
        )

    def test_environment_error_raised_when_password_missing(self):
        del os.environ[Factory.POSTGRES_PASSWORD]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct("TestCase")
        self.assertEqual(
            cm.exception.args[0],
            "Postgres password not found in environment with key 'POSTGRES_PASSWORD'",
        )

    def test_env_create_table(self):
        self.factory = InfrastructureFactory.construct("TestCase")
        self.assertTrue(self.factory.env_create_table())
        os.environ[Factory.CREATE_TABLE] = "y"
        self.assertTrue(self.factory.env_create_table())
        os.environ[Factory.CREATE_TABLE] = "n"
        self.factory = InfrastructureFactory.construct("TestCase")
        self.assertFalse(self.factory.env_create_table())


async def drop_postgres_table(datastore: AsyncPostgresDatastore, table_name):
    await datastore  # For when connection pool hasn't already been initialised.
    try:
        async with datastore.pool.acquire() as connection:
            # Open a transaction.
            async with connection.transaction():
                # Run the query passing the request argument.
                statement = f"DROP TABLE {table_name} CASCADE;"
                await connection.fetch(statement)
    except UndefinedTableError:
        pass


async def drop_postgres_function(datastore: AsyncPostgresDatastore, function_name):
    await datastore  # For when connection pool hasn't already been initialised.
    try:
        async with datastore.pool.acquire() as connection:
            # Open a transaction.
            async with connection.transaction():
                # Run the query passing the request argument.
                statement = f"DROP FUNCTION {function_name};"
                await connection.fetch(statement)
    except UndefinedFunctionError:
        pass


del AsyncAggregateRecorderTestCase
del AsyncApplicationRecorderTestCase
del AsyncProcessRecorderTestCase
del InfrastructureFactoryTestCase
