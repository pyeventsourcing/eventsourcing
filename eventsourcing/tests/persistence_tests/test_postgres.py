from threading import Event, Thread
from time import sleep
from typing import List
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
from psycopg import Connection

from eventsourcing.persistence import (
    DatabaseError,
    DataError,
    InfrastructureFactory,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    PersistenceError,
    ProgrammingError,
    StoredEvent,
    Tracking,
)
from eventsourcing.postgres import (
    Factory,
    PostgresAggregateRecorder,
    PostgresApplicationRecorder,
    PostgresConnection,
    PostgresConnectionPool,
    PostgresCursor,
    PostgresDatastore,
    PostgresProcessRecorder,
    PostgresTransaction,
)
from eventsourcing.tests.persistence import (
    AggregateRecorderTestCase,
    ApplicationRecorderTestCase,
    InfrastructureFactoryTestCase,
    ProcessRecorderTestCase,
)
from eventsourcing.tests.persistence_tests.test_connection_pool import (
    TestConnectionPool,
)
from eventsourcing.tests.postgres_utils import (
    drop_postgres_table,
    pg_close_all_connections,
)
from eventsourcing.utils import Environment


class TestPostgresConnection(TestCase):
    def setUp(self) -> None:
        self.mock_pg_conn = MagicMock(Connection)
        self.mock_pg_conn.closed = False

        def set_pg_conn_closed():
            self.mock_pg_conn.closed = True

        self.mock_pg_conn.close.side_effect = set_pg_conn_closed
        self.conn = PostgresConnection(pg_conn=self.mock_pg_conn, max_age=1)

    def test_cursor(self):
        self.assertEqual(0, self.mock_pg_conn.cursor.call_count)
        curs = self.conn.cursor()
        self.assertIsInstance(curs, PostgresCursor)
        self.assertEqual(1, self.mock_pg_conn.cursor.call_count)

    def test_commit(self):
        self.assertEqual(0, self.mock_pg_conn.commit.call_count)
        self.conn.commit()
        self.assertEqual(1, self.mock_pg_conn.commit.call_count)

    def test_rollback(self):
        self.assertEqual(0, self.mock_pg_conn.rollback.call_count)
        self.conn.rollback()
        self.assertEqual(1, self.mock_pg_conn.rollback.call_count)

    def test_close(self):
        self.assertEqual(0, self.mock_pg_conn.close.call_count)
        self.assertFalse(self.conn.closed)
        self.conn.close()
        self.assertEqual(1, self.mock_pg_conn.close.call_count)
        self.assertTrue(self.conn.closed)

    def test_transaction(self):
        with self.conn.transaction(commit=False) as transaction:
            self.assertIsInstance(transaction, PostgresTransaction)
        self.assertEqual(0, self.mock_pg_conn.commit.call_count)

        with self.conn.transaction(commit=True) as transaction:
            self.assertIsInstance(transaction, PostgresTransaction)
            self.assertEqual(0, self.mock_pg_conn.commit.call_count)
        self.assertEqual(1, self.mock_pg_conn.commit.call_count)


class TestPostgresConnectionPool(TestConnectionPool):
    ProgrammingError = psycopg.ProgrammingError
    PersistenceError = psycopg.Error
    allowed_connecting_time = 0.02
    expected_result_from_select_1 = [{"?column?": 1}]

    def create_pool(
        self,
        pool_size=1,
        max_overflow=0,
        max_age=None,
        pre_ping=False,
        mutually_exclusive_read_write=True,
    ):
        return PostgresConnectionPool(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
            pool_size=pool_size,
            max_overflow=max_overflow,
            max_age=max_age,
            pre_ping=pre_ping,
        )

    def close_connection_on_server(self, *connections):
        # Close all connections.
        pg_close_all_connections()

    def test_get_connection(self):
        # Check we can get a postgres connection.
        pool = self.create_pool()
        conn = pool.get_connection()
        self.assertIsInstance(conn, PostgresConnection)

    def test_bad_connection_config(self):
        pool = PostgresConnectionPool(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="4321",
            user="eventsourcing",
            password="eventsourcing",
        )
        with self.assertRaises(OperationalError):
            pool.get_connection()

    def test_close_on_server_after_returning_with_pre_ping(self):
        super().test_close_on_server_after_returning_with_pre_ping()

    def test_close_on_server_after_returning_without_pre_ping(self):
        super().test_close_on_server_after_returning_without_pre_ping()

    def test_reader_writer(self):
        self.skipTest("Recorders don't use reader/writer exclusion mechanism")


class TestPostgresTransaction(TestCase):
    def setUp(self) -> None:
        self.conn = MagicMock(PostgresConnection)
        self.transaction = PostgresTransaction(self.conn, commit=True)

    def test_cursor(self):
        self.assertEqual(0, self.conn.cursor.call_count)
        self.transaction.cursor()
        self.assertEqual(1, self.conn.cursor.call_count)

    def test_calls_commit_if_error_not_raised_during_transaction(self):
        with self.transaction:
            pass
        self.conn.commit.assert_called()
        self.conn.rollback.assert_not_called()

    def test_calls_rollback_if_error_is_raised_during_transaction(self):
        with self.assertRaises(TypeError):
            with self.transaction:
                raise TypeError
        self.conn.commit.assert_not_called()
        self.conn.rollback.assert_called()

    def test_calls_rollback_if_commit_arg_is_false(self):
        # Avoid traceback error from Transaction.__del__.
        self.transaction.has_entered = True

        # Create transaction with commit=False.
        self.transaction = PostgresTransaction(self.conn, commit=False)
        with self.transaction:
            pass
        self.conn.commit.assert_not_called()
        self.conn.rollback.assert_called()


class TestPostgresDatastore(TestCase):
    def test_is_pipeline_supported(self):
        self.assertTrue(psycopg.Pipeline.is_supported())

    def test_has_connection_pool(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        self.assertIsInstance(datastore.pool, PostgresConnectionPool)

    def test_get_connection(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        with datastore.get_connection() as conn:
            self.assertIsInstance(conn, PostgresConnection)

    def test_context_manager_converts_exceptions_and_conditionally_calls_close(self):
        cases = [
            (InterfaceError, psycopg.InterfaceError(), True),
            (DataError, psycopg.DataError(), False),
            (OperationalError, psycopg.OperationalError(), True),
            (IntegrityError, psycopg.IntegrityError(), False),
            (InternalError, psycopg.InternalError(), False),
            (ProgrammingError, psycopg.ProgrammingError(), False),
            (NotSupportedError, psycopg.NotSupportedError(), False),
            (DatabaseError, psycopg.DatabaseError(), False),
            (PersistenceError, psycopg.Error(), True),
            (TypeError, TypeError(), True),
            (TypeError, TypeError, True),
        ]
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        for expected_exc_type, raised_exc, expect_conn_closed in cases:
            with self.assertRaises(expected_exc_type):
                with datastore.get_connection() as conn:
                    self.assertFalse(conn.closed)
                    raise raised_exc
                self.assertTrue(conn.closed is expect_conn_closed, raised_exc)

    def test_transactions_from_connection(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        # We can do several transactions with a connection.
        with datastore.get_connection() as conn:
            # Transaction 1.
            with conn.transaction(commit=False), conn.cursor() as curs:
                curs.execute("SELECT 1")
                self.assertEqual(curs.fetchall(), [{"?column?": 1}])

            # Transaction 2.
            with conn.transaction(commit=True), conn.cursor() as curs:
                curs.execute("SELECT 1")
                self.assertEqual(curs.fetchall(), [{"?column?": 1}])

            # Transaction 3.
            with conn.transaction(commit=True), conn.cursor() as curs:
                curs.execute("SELECT 1")
                self.assertEqual(curs.fetchall(), [{"?column?": 1}])

    def test_transaction_from_datastore(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        # As a convenience, we can use the transaction() method.
        with datastore.transaction(commit=False) as curs:
            curs.execute("SELECT 1")
            self.assertEqual(curs.fetchall(), [{"?column?": 1}])

    def test_connect_failure_raises_operational_error(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="4321",  # wrong port
            user="eventsourcing",
            password="eventsourcing",
        )
        with self.assertRaises(OperationalError):
            with datastore.get_connection():
                pass

        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="987654321",  # bad value
            user="eventsourcing",
            password="eventsourcing",
        )
        with self.assertRaises(OperationalError):
            with datastore.get_connection():
                pass

    def test_pre_ping(self):
        # Define method to open and close a connection, and then execute a statement.
        def open_close_execute(pre_ping: bool):
            datastore = PostgresDatastore(
                dbname="eventsourcing",
                host="127.0.0.1",
                port="5432",
                user="eventsourcing",
                password="eventsourcing",
                pool_size=1,
                pre_ping=pre_ping,
            )

            # Create a connection.
            with datastore.get_connection() as conn:
                pass

                # Check the connection works.
                with conn.cursor() as curs:
                    curs.execute("SELECT 1")
                    self.assertEqual(curs.fetchall(), [{"?column?": 1}])

            # Close all connections via separate connection.
            pg_close_all_connections()

            # Check the connection doesn't think it's closed.
            self.assertTrue(datastore.pool._pool)
            self.assertFalse(datastore.pool._pool[0].closed)

            # Get a closed connection.
            with datastore.get_connection() as conn:
                self.assertFalse(conn.closed)

                with conn.cursor() as curs:
                    curs.execute("SELECT 1")

        # Check using the closed connection gives an error.
        with self.assertRaises(OperationalError):
            open_close_execute(pre_ping=False)

        # Now try that again with pre-ping enabled.
        open_close_execute(pre_ping=True)

    def test_idle_in_transaction_session_timeout(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
            idle_in_transaction_session_timeout=1,
        )
        with self.assertRaises(PersistenceError):
            with datastore.transaction(commit=False) as curs:
                curs.execute("SELECT 1")
                self.assertFalse(curs.closed)
                sleep(2)


# Use maximally long identifier for table name.
EVENTS_TABLE_NAME = "s" * 50 + "stored_events"
assert len(EVENTS_TABLE_NAME) == 63


class SetupPostgresDatastore(TestCase):
    schema = ""

    def setUp(self) -> None:
        super().setUp()
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
            schema=self.schema,
        )
        self.drop_tables()

    def tearDown(self) -> None:
        super().tearDown()
        self.drop_tables()

    def drop_tables(self):
        events_table_name = EVENTS_TABLE_NAME
        if self.datastore.schema:
            events_table_name = f"{self.datastore.schema}.{events_table_name}"
        drop_postgres_table(self.datastore, events_table_name)


class WithSchema(SetupPostgresDatastore):
    schema = "myschema"

    def test_datastore_has_schema(self):
        self.assertEqual(self.datastore.schema, self.schema)


class TestPostgresAggregateRecorder(SetupPostgresDatastore, AggregateRecorderTestCase):
    def create_recorder(
        self, table_name=EVENTS_TABLE_NAME
    ) -> PostgresAggregateRecorder:
        if self.datastore.schema:
            table_name = f"{self.datastore.schema}.{table_name}"
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name=table_name
        )
        recorder.create_table()
        return recorder

    def drop_tables(self):
        super().drop_tables()
        drop_postgres_table(self.datastore, "stored_events")

    def test_create_table(self):
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()

    def test_insert_and_select(self):
        super().test_insert_and_select()

    def test_performance(self):
        super().test_performance()

    def test_retry_insert_events_after_closing_connection(self):
        # This checks connection is recreated after connections are closed.
        self.datastore.pool.pool_size = 1

        # Construct the recorder.
        recorder = self.create_recorder()

        # Check we have open connections.
        self.assertTrue(self.datastore.pool._pool)

        # Close connections.
        pg_close_all_connections()
        self.assertFalse(self.datastore.pool._pool[0].closed)

        # Write a stored event.
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        recorder.insert_events([stored_event1])

    # def test_retry_insert_events_after_deallocating_prepared_statement(self):
    #     # !!! In psycopg this condition now raises a ProgrammingError lol
    #     # This checks connection is recreated after OperationalError.
    #
    #     # Construct the recorder.
    #     recorder = self.create_recorder()
    #     self.datastore.pool.pool_size = 1
    #
    #     # Write a stored event.
    #     stored_event1 = StoredEvent(
    #         originator_id=uuid4(),
    #         originator_version=0,
    #         topic="topic1",
    #         state=b"state1",
    #     )
    #     recorder.insert_events([stored_event1])
    #
    #     # Deallocate the prepared insert statement.
    #     self.assertTrue(self.datastore.pool._pool)
    #     with self.datastore.get_connection() as conn:
    #         statement_name = recorder.insert_events_statement_name
    #         self.assertIn(statement_name, conn.is_prepared)
    #         conn.cursor().execute(
    #             f"DEALLOCATE " f"{recorder.statement_name_aliases[statement_name]}"
    #         )
    #
    #     # Write a stored event.
    #     stored_event2 = StoredEvent(
    #         originator_id=uuid4(),
    #         originator_version=1,
    #         topic="topic2",
    #         state=b"state2",
    #     )
    #     recorder.insert_events([stored_event2])
    #
    # def test_retry_select_events_after_closing_connection(self):
    #     # !!! In psycopg this condition now raises a ProgrammingError lol
    #     # This checks connection is recreated after being closed on the server.
    #
    #     # Construct the recorder.
    #     recorder = self.create_recorder()
    #     self.datastore.pool.pool_size = 1
    #
    #     # Write a stored event.
    #     originator_id = uuid4()
    #     stored_event1 = StoredEvent(
    #         originator_id=originator_id,
    #         originator_version=0,
    #         topic="topic1",
    #         state=b"state1",
    #     )
    #     recorder.insert_events([stored_event1])
    #
    #     # Close connections.
    #     pg_close_all_connections()
    #     self.assertFalse(self.datastore.pool._pool[0].closed)
    #
    #     # Select events.
    #     recorder.select_events(originator_id)

    # def test_retry_select_events_after_deallocating_prepared_statement(self):
    #     # !!! In psycopg this condition now raises a ProgrammingError lol
    #     # This checks connection is recreated after OperationalError.
    #
    #     # Construct the recorder.
    #     recorder = self.create_recorder()
    #     self.datastore.pool.pool_size = 1
    #
    #     # Write a stored event.
    #     originator_id = uuid4()
    #     stored_event1 = StoredEvent(
    #         originator_id=originator_id,
    #         originator_version=0,
    #         topic="topic1",
    #         state=b"state1",
    #     )
    #     recorder.insert_events([stored_event1])
    #
    #     # Select events.
    #     recorder.select_events(originator_id)
    #
    #     # Deallocate the prepared select statement.
    #     with self.datastore.get_connection() as conn:
    #         if self.schema:
    #             statement_name = f"select_{self.schema}_{EVENTS_TABLE_NAME}"
    #         else:
    #             statement_name = f"select_{EVENTS_TABLE_NAME}"
    #         self.assertIn(statement_name, conn.is_prepared)
    #         conn.cursor().execute(
    #             f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
    #         )
    #
    #     # Select events.
    #     recorder.select_events(originator_id)


class TestPostgresAggregateRecorderWithSchema(
    WithSchema, TestPostgresAggregateRecorder
):
    pass


class TestPostgresAggregateRecorderErrors(SetupPostgresDatastore, TestCase):
    def create_recorder(self, table_name=EVENTS_TABLE_NAME):
        return PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name=table_name
        )

    def test_excessively_long_table_name_raises_error(self):
        # Add one more character to the table name.
        long_table_name = "s" + EVENTS_TABLE_NAME
        self.assertEqual(len(long_table_name), 64)
        with self.assertRaises(ProgrammingError):
            self.create_recorder(long_table_name)

    def test_create_table_raises_programming_error_when_sql_is_broken(self):
        recorder = self.create_recorder()

        # Mess up the statement.
        recorder.create_table_statements = ["BLAH"]
        with self.assertRaises(ProgrammingError):
            recorder.create_table()

    def test_insert_events_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Write a stored event without creating the table.
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        with self.assertRaises(ProgrammingError):
            recorder.insert_events([stored_event1])

    def test_insert_events_raises_programming_error_when_sql_is_broken(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Create the table.
        recorder.create_table()

        # Write a stored event with broken statement.
        recorder.insert_events_statement = "BLAH"
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        with self.assertRaises(ProgrammingError):
            recorder.insert_events([stored_event1])

    def test_select_events_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Select events without creating the table.
        originator_id = uuid4()
        with self.assertRaises(ProgrammingError):
            recorder.select_events(originator_id=originator_id)

    def test_select_events_raises_programming_error_when_sql_is_broken(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Create the table.
        recorder.create_table()

        # Select events with broken statement.
        recorder.select_events_statement = "BLAH"
        originator_id = uuid4()
        with self.assertRaises(ProgrammingError):
            recorder.select_events(originator_id=originator_id)


class TestPostgresApplicationRecorder(
    SetupPostgresDatastore, ApplicationRecorderTestCase
):
    def create_recorder(
        self, table_name=EVENTS_TABLE_NAME
    ) -> PostgresApplicationRecorder:
        if self.datastore.schema:
            table_name = f"{self.datastore.schema}.{table_name}"
        recorder = PostgresApplicationRecorder(
            self.datastore, events_table_name=table_name
        )
        recorder.create_table()
        return recorder

    def test_insert_select(self) -> None:
        super().test_insert_select()

    def test_concurrent_no_conflicts(self):
        super().test_concurrent_no_conflicts()

    def test_concurrent_throughput(self):
        self.datastore.pool.pool_size = 4
        super().test_concurrent_throughput()

    def test_retry_select_notifications_after_closing_connection(self):
        # This checks connection is recreated after InterfaceError.

        # Construct the recorder.
        recorder = self.create_recorder()
        self.datastore.pool.pool_size = 1

        # Write a stored event.
        originator_id = uuid4()
        stored_event1 = StoredEvent(
            originator_id=originator_id,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        recorder.insert_events([stored_event1])

        # Close connections.
        pg_close_all_connections()
        self.assertFalse(self.datastore.pool._pool[0].closed)

        # Select events.
        recorder.select_notifications(start=1, limit=1)

    # def test_retry_select_notifications_after_deallocating_prepared_statement(self):
    #     # !!! In psycopg this condition now raises a ProgrammingError lol
    #     # This checks connection is recreated after OperationalError.
    #
    #     # Construct the recorder.
    #     recorder = self.create_recorder()
    #     self.datastore.pool.pool_size = 1
    #
    #     # Write a stored event.
    #     originator_id = uuid4()
    #     stored_event1 = StoredEvent(
    #         originator_id=originator_id,
    #         originator_version=0,
    #         topic="topic1",
    #         state=b"state1",
    #     )
    #     recorder.insert_events([stored_event1])
    #
    #     # Select notifications.
    #     recorder.select_notifications(start=1, limit=1)
    #
    #     # Deallocate prepared statement.
    #     self.assertTrue(self.datastore.pool._pool)
    #     with self.datastore.get_connection() as conn:
    #         statement_name = (
    #             f"select_notifications_{recorder.events_table_name}".replace(".", "_")
    #         )
    #         self.assertIn(statement_name, conn.is_prepared)
    #         conn.cursor().execute(
    #             f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
    #         )
    #
    #     # Select notifications.
    #     recorder.select_notifications(start=1, limit=1)

    def test_retry_max_notification_id_after_closing_connection(self):
        # This checks connection is recreated after InterfaceError.

        # Construct the recorder.
        recorder = self.create_recorder()
        self.datastore.pool.pool_size = 1

        # Write a stored event.
        originator_id = uuid4()
        stored_event1 = StoredEvent(
            originator_id=originator_id,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        recorder.insert_events([stored_event1])

        # Close connections.
        pg_close_all_connections()
        self.assertFalse(self.datastore.pool._pool[0].closed)

        # Get max notification ID.
        recorder.max_notification_id()

    # def test_retry_max_notification_id_after_deallocating_prepared_statement(self):
    #     # !!! In psycopg this condition now raises a ProgrammingError lol
    #     # This checks connection is recreated after OperationalError.
    #
    #     # Construct the recorder.
    #     recorder = self.create_recorder()
    #     self.datastore.pool.pool_size = 1
    #
    #     # Write a stored event.
    #     originator_id = uuid4()
    #     stored_event1 = StoredEvent(
    #         originator_id=originator_id,
    #         originator_version=0,
    #         topic="topic1",
    #         state=b"state1",
    #     )
    #     recorder.insert_events([stored_event1])
    #
    #     # Get max notification ID.
    #     recorder.max_notification_id()
    #
    #     # Deallocate prepared statement.
    #     self.assertTrue(self.datastore.pool._pool)
    #     if self.schema:
    #         qualified_table_name = f"{self.schema}.{EVENTS_TABLE_NAME}"
    #     else:
    #         qualified_table_name = f"{EVENTS_TABLE_NAME}"
    #     statement_name = f"max_notification_id_{qualified_table_name}".replace(".", "_")
    #     for conn in self.datastore.pool._pool:
    #         self.assertIn(statement_name, conn.is_prepared)
    #         conn.cursor().execute(
    #             f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
    #         )
    #
    #     # Get max notification ID.
    #     recorder.max_notification_id()

    def test_insert_lock_timeout_actually_works(self):
        self.datastore.lock_timeout = 1
        recorder: PostgresApplicationRecorder = self.create_recorder()

        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=1,
            topic="topic1",
            state=b"state1",
        )
        stored_event2 = StoredEvent(
            originator_id=uuid4(),
            originator_version=1,
            topic="topic1",
            state=b"state1",
        )

        table_lock_acquired = Event()
        test_ended = Event()
        table_lock_timed_out = Event()

        def insert1():
            with self.datastore.get_connection() as conn:
                with conn.transaction(commit=True), conn.cursor() as curs:
                    # Lock table.
                    recorder._insert_stored_events(curs, [stored_event1])
                    table_lock_acquired.set()
                    # Wait for other thread to timeout.
                    test_ended.wait(timeout=5)  # keep the lock

        def insert2():
            try:
                with self.datastore.get_connection() as conn:
                    # Wait for other thread to lock table.
                    table_lock_acquired.wait(timeout=5)
                    # Expect to timeout.
                    with conn.transaction(commit=True), conn.cursor() as curs:
                        recorder._insert_stored_events(curs, [stored_event2])
            except OperationalError as e:
                if "lock timeout" in e.args[0]:
                    table_lock_timed_out.set()

        thread1 = Thread(target=insert1, daemon=True)
        thread1.start()
        thread2 = Thread(target=insert2, daemon=True)
        thread2.start()

        table_lock_timed_out.wait(timeout=4)
        test_ended.set()

        thread1.join(timeout=10)
        thread2.join(timeout=10)

        self.assertTrue(table_lock_timed_out.is_set())


class TestPostgresApplicationRecorderWithSchema(
    WithSchema, TestPostgresApplicationRecorder
):
    pass


class TestPostgresApplicationRecorderErrors(SetupPostgresDatastore, TestCase):
    def create_recorder(self, table_name=EVENTS_TABLE_NAME):
        return PostgresApplicationRecorder(self.datastore, events_table_name=table_name)

    def test_excessively_long_table_name_raises_error(self):
        # Add one more character to the table name.
        long_table_name = "s" + EVENTS_TABLE_NAME
        self.assertEqual(len(long_table_name), 64)
        with self.assertRaises(ProgrammingError):
            self.create_recorder(long_table_name)

    def test_select_notification_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Select notifications without creating table.
        with self.assertRaises(ProgrammingError):
            recorder.select_notifications(start=1, limit=1)

    def test_max_notification_id_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name=EVENTS_TABLE_NAME
        )

        # Select notifications without creating table.
        with self.assertRaises(ProgrammingError):
            recorder.max_notification_id()

    def test_fetch_ids_after_insert_events(self):
        def make_events() -> List[StoredEvent]:
            return [
                StoredEvent(
                    originator_id=uuid4(),
                    originator_version=1,
                    state=b"",
                    topic="",
                )
            ]

        #
        # Check it actually works.
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name=EVENTS_TABLE_NAME
        )
        recorder.create_table()
        max_notification_id = recorder.max_notification_id()
        notification_ids = recorder.insert_events(make_events())
        self.assertEqual(len(notification_ids), 1)
        self.assertEqual(max_notification_id + 1, notification_ids[0])

        # Events but no lock table statements.
        with self.assertRaises(ProgrammingError):
            recorder = PostgresApplicationRecorder(
                datastore=self.datastore, events_table_name=EVENTS_TABLE_NAME
            )
            recorder.create_table()
            recorder.lock_table_statements = []
            recorder.insert_events(make_events())

        return


TRACKING_TABLE_NAME = "n" * 42 + "notification_tracking"
assert len(TRACKING_TABLE_NAME) == 63


class TestPostgresProcessRecorder(SetupPostgresDatastore, ProcessRecorderTestCase):
    def drop_tables(self):
        super().drop_tables()
        tracking_table_name = TRACKING_TABLE_NAME
        if self.datastore.schema:
            tracking_table_name = f"{self.datastore.schema}.{tracking_table_name}"
        drop_postgres_table(self.datastore, tracking_table_name)

    def create_recorder(self):
        events_table_name = EVENTS_TABLE_NAME
        tracking_table_name = TRACKING_TABLE_NAME
        if self.datastore.schema:
            events_table_name = f"{self.datastore.schema}.{events_table_name}"
        if self.datastore.schema:
            tracking_table_name = f"{self.datastore.schema}.{tracking_table_name}"
        recorder = PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            tracking_table_name=tracking_table_name,
        )
        recorder.create_table()
        return recorder

    def test_insert_select(self):
        super().test_insert_select()

    def test_performance(self):
        super().test_performance()

    def test_excessively_long_table_names_raise_error(self):
        with self.assertRaises(ProgrammingError):
            PostgresProcessRecorder(
                datastore=self.datastore,
                events_table_name="e" + EVENTS_TABLE_NAME,
                tracking_table_name=TRACKING_TABLE_NAME,
            )

        with self.assertRaises(ProgrammingError):
            PostgresProcessRecorder(
                datastore=self.datastore,
                events_table_name=EVENTS_TABLE_NAME,
                tracking_table_name="n" + TRACKING_TABLE_NAME,
            )

    def test_retry_max_tracking_id_after_closing_connection(self):
        # This checks connection is recreated after InterfaceError.

        # Construct the recorder.
        recorder = self.create_recorder()
        self.datastore.pool.pool_size = 1

        # Write a tracking record.
        originator_id = uuid4()
        stored_event1 = StoredEvent(
            originator_id=originator_id,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        recorder.insert_events([stored_event1], tracking=Tracking("upstream", 1))

        # Close connections.
        pg_close_all_connections()
        self.assertFalse(self.datastore.pool._pool[0].closed)

        # Get max tracking ID.
        notification_id = recorder.max_tracking_id("upstream")
        self.assertEqual(notification_id, 1)

    # def test_retry_max_tracking_id_after_deallocating_prepared_statement(self):
    #     # !!! In psycopg this condition now raises a ProgrammingError lol
    #     # This checks connection is recreated after OperationalError.
    #
    #     # Construct the recorder.
    #     recorder = self.create_recorder()
    #     self.datastore.pool.pool_size = 1
    #
    #     # Write a tracking record.
    #     originator_id = uuid4()
    #     stored_event1 = StoredEvent(
    #         originator_id=originator_id,
    #         originator_version=0,
    #         topic="topic1",
    #         state=b"state1",
    #     )
    #     recorder.insert_events([stored_event1], tracking=Tracking("upstream", 1))
    #
    #     # Get max tracking ID.
    #     notification_id = recorder.max_tracking_id("upstream")
    #     self.assertEqual(notification_id, 1)
    #
    #     # Deallocate prepared statement.
    #     self.assertTrue(self.datastore.pool._pool)
    #     with self.datastore.get_connection() as conn:
    #         statement_name = recorder.max_tracking_id_statement_name
    #         self.assertIn(statement_name, conn.is_prepared)
    #         conn.cursor().execute(
    #             f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
    #         )
    #
    #     # Get max tracking ID.
    #     notification_id = recorder.max_tracking_id("upstream")
    #     self.assertEqual(notification_id, 1)


class TestPostgresProcessRecorderWithSchema(WithSchema, TestPostgresProcessRecorder):
    pass


class TestPostgresProcessRecorderErrors(SetupPostgresDatastore, TestCase):
    def drop_tables(self):
        super().drop_tables()
        drop_postgres_table(self.datastore, TRACKING_TABLE_NAME)

    def create_recorder(self):
        return PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name=EVENTS_TABLE_NAME,
            tracking_table_name=TRACKING_TABLE_NAME,
        )

    def test_max_tracking_id_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Get max tracking ID without creating table.
        with self.assertRaises(ProgrammingError):
            recorder.max_tracking_id("upstream")


class TestPostgresInfrastructureFactory(InfrastructureFactoryTestCase):
    def test_create_application_recorder(self):
        super().test_create_application_recorder()

    def expected_factory_class(self):
        return Factory

    def expected_aggregate_recorder_class(self):
        return PostgresAggregateRecorder

    def expected_application_recorder_class(self):
        return PostgresApplicationRecorder

    def expected_process_recorder_class(self):
        return PostgresProcessRecorder

    def setUp(self) -> None:
        self.env = Environment("TestCase")
        self.env[InfrastructureFactory.PERSISTENCE_MODULE] = Factory.__module__
        self.env[Factory.POSTGRES_DBNAME] = "eventsourcing"
        self.env[Factory.POSTGRES_HOST] = "127.0.0.1"
        self.env[Factory.POSTGRES_PORT] = "5432"
        self.env[Factory.POSTGRES_USER] = "eventsourcing"
        self.env[Factory.POSTGRES_PASSWORD] = "eventsourcing"
        self.drop_tables()
        super().setUp()

    def tearDown(self) -> None:
        self.drop_tables()
        super().tearDown()

    def drop_tables(self):
        datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        drop_postgres_table(datastore, "testcase_events")
        drop_postgres_table(datastore, "testcase_tracking")

    def test_close(self):
        factory = Factory(self.env)
        self.assertFalse(factory.datastore.pool.closed)
        factory.close()
        self.assertTrue(factory.datastore.pool.closed)

    def test_conn_max_age_is_set_to_empty_string(self):
        self.env[Factory.POSTGRES_CONN_MAX_AGE] = ""
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.max_age, None)

    def test_conn_max_age_is_set_to_number(self):
        self.env[Factory.POSTGRES_CONN_MAX_AGE] = "0"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.max_age, 0)

    def test_pool_size_is_five_by_default(self):
        self.assertTrue(Factory.POSTGRES_POOL_SIZE not in self.env)
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pool_size, 5)

        self.env[Factory.POSTGRES_POOL_SIZE] = ""
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pool_size, 5)

    def test_max_overflow_is_ten_by_default(self):
        self.assertTrue(Factory.POSTGRES_POOL_MAX_OVERFLOW not in self.env)
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.max_overflow, 10)

        self.env[Factory.POSTGRES_POOL_MAX_OVERFLOW] = ""
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.max_overflow, 10)

    def test_max_overflow_is_set(self):
        self.env[Factory.POSTGRES_POOL_MAX_OVERFLOW] = "7"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.max_overflow, 7)

    def test_pool_size_is_Set(self):
        self.env[Factory.POSTGRES_POOL_SIZE] = "6"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pool_size, 6)

    def test_connect_timeout_is_five_by_default(self):
        self.assertTrue(Factory.POSTGRES_CONNECT_TIMEOUT not in self.env)
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.connect_timeout, 5)

        self.env[Factory.POSTGRES_CONNECT_TIMEOUT] = ""
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.connect_timeout, 5)

    def test_connect_timeout_is_set(self):
        self.env[Factory.POSTGRES_CONNECT_TIMEOUT] = "8"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.connect_timeout, 8)

    def test_pool_timeout_is_30_by_default(self):
        self.assertTrue(Factory.POSTGRES_POOL_TIMEOUT not in self.env)
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pool_timeout, 30)

        self.env[Factory.POSTGRES_POOL_TIMEOUT] = ""
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pool_timeout, 30)

    def test_pool_timeout_is_set(self):
        self.env[Factory.POSTGRES_POOL_TIMEOUT] = "8"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pool_timeout, 8)

    def test_lock_timeout_is_zero_by_default(self):
        self.assertTrue(Factory.POSTGRES_LOCK_TIMEOUT not in self.env)
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.lock_timeout, 0)

        self.env[Factory.POSTGRES_LOCK_TIMEOUT] = ""
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.lock_timeout, 0)

    def test_lock_timeout_is_set(self):
        self.env[Factory.POSTGRES_LOCK_TIMEOUT] = "1"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.lock_timeout, 1)

    def test_idle_in_transaction_session_timeout_is_5_by_default(self):
        self.assertTrue(
            Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT not in self.env
        )
        self.factory = Factory(self.env)
        self.assertEqual(
            self.factory.datastore.pool.idle_in_transaction_session_timeout, 5
        )
        self.factory.close()

        self.env[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = ""
        self.factory = Factory(self.env)
        self.assertEqual(
            self.factory.datastore.pool.idle_in_transaction_session_timeout, 5
        )

    def test_idle_in_transaction_session_timeout_is_set(self):
        self.env[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = "10"
        self.factory = Factory(self.env)
        self.assertEqual(
            self.factory.datastore.pool.idle_in_transaction_session_timeout, 10
        )

    def test_pre_ping_off_by_default(self):
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pre_ping, False)

    def test_pre_ping_off(self):
        self.env[Factory.POSTGRES_PRE_PING] = "off"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pre_ping, False)

    def test_pre_ping_on(self):
        self.env[Factory.POSTGRES_PRE_PING] = "on"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.pool.pre_ping, True)

    def test_environment_error_raised_when_conn_max_age_not_a_float(self):
        self.env[Factory.POSTGRES_CONN_MAX_AGE] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_CONN_MAX_AGE' "
            "is invalid. If set, a float or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_connect_timeout_not_an_integer(self):
        self.env[Factory.POSTGRES_CONNECT_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_CONNECT_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_pool_timeout_not_an_integer(self):
        self.env[Factory.POSTGRES_POOL_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_POOL_TIMEOUT' "
            "is invalid. If set, a float or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_lock_timeout_not_an_integer(self):
        self.env[Factory.POSTGRES_LOCK_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_LOCK_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_min_conn_not_an_integer(self):
        self.env[Factory.POSTGRES_POOL_SIZE] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_POOL_SIZE' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_max_conn_not_an_integer(self):
        self.env[Factory.POSTGRES_POOL_MAX_OVERFLOW] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_POOL_MAX_OVERFLOW' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_idle_in_transaction_session_timeout_not_an_integer(
        self,
    ):
        self.env[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key "
            "'POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_dbname_missing(self):
        del self.env[Factory.POSTGRES_DBNAME]
        with self.assertRaises(EnvironmentError) as cm:
            InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres database name not found in environment "
            "with key 'POSTGRES_DBNAME'",
        )

    def test_environment_error_raised_when_dbhost_missing(self):
        del self.env[Factory.POSTGRES_HOST]
        with self.assertRaises(EnvironmentError) as cm:
            InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres host not found in environment with key 'POSTGRES_HOST'",
        )

    def test_environment_error_raised_when_user_missing(self):
        del self.env[Factory.POSTGRES_USER]
        with self.assertRaises(EnvironmentError) as cm:
            InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres user not found in environment with key 'POSTGRES_USER'",
        )

    def test_environment_error_raised_when_password_missing(self):
        del self.env[Factory.POSTGRES_PASSWORD]
        with self.assertRaises(EnvironmentError) as cm:
            InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres password not found in environment with key 'POSTGRES_PASSWORD'",
        )

    def test_schema_set_to_empty_string(self):
        self.env[Factory.POSTGRES_SCHEMA] = ""
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.schema, "")

    def test_schema_set_to_whitespace(self):
        self.env[Factory.POSTGRES_SCHEMA] = " "
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.schema, "")

    def test_scheme_adjusts_table_names_on_aggregate_recorder(self):
        self.factory = Factory(self.env)

        # Check by default the table name is not qualified.
        recorder = self.factory.aggregate_recorder("events")
        assert isinstance(recorder, PostgresAggregateRecorder)
        self.assertEqual(recorder.events_table_name, "testcase_events")

        # Check by default the table name is not qualified.
        recorder = self.factory.aggregate_recorder("snapshots")
        assert isinstance(recorder, PostgresAggregateRecorder)
        self.assertEqual(recorder.events_table_name, "testcase_snapshots")

        # Set schema in environment.
        self.env[Factory.POSTGRES_SCHEMA] = "public"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.schema, "public")

        # Check by default the table name is qualified.
        recorder = self.factory.aggregate_recorder("events")
        assert isinstance(recorder, PostgresAggregateRecorder)
        self.assertEqual(recorder.events_table_name, "public.testcase_events")

        # Check by default the table name is qualified.
        recorder = self.factory.aggregate_recorder("snapshots")
        assert isinstance(recorder, PostgresAggregateRecorder)
        self.assertEqual(recorder.events_table_name, "public.testcase_snapshots")

    def test_scheme_adjusts_table_name_on_application_recorder(self):
        self.factory = Factory(self.env)

        # Check by default the table name is not qualified.
        recorder = self.factory.application_recorder()
        assert isinstance(recorder, PostgresApplicationRecorder)
        self.assertEqual(recorder.events_table_name, "testcase_events")

        # Set schema in environment.
        self.env[Factory.POSTGRES_SCHEMA] = "public"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.schema, "public")

        # Check by default the table name is qualified.
        recorder = self.factory.application_recorder()
        assert isinstance(recorder, PostgresApplicationRecorder)
        self.assertEqual(recorder.events_table_name, "public.testcase_events")

    def test_scheme_adjusts_table_names_on_process_recorder(self):
        self.factory = Factory(self.env)

        # Check by default the table name is not qualified.
        recorder = self.factory.process_recorder()
        assert isinstance(recorder, PostgresProcessRecorder)
        self.assertEqual(recorder.events_table_name, "testcase_events")
        self.assertEqual(recorder.tracking_table_name, "testcase_tracking")

        # Set schema in environment.
        self.env[Factory.POSTGRES_SCHEMA] = "public"
        self.factory = Factory(self.env)
        self.assertEqual(self.factory.datastore.schema, "public")

        # Check by default the table name is qualified.
        recorder = self.factory.process_recorder()
        assert isinstance(recorder, PostgresProcessRecorder)
        self.assertEqual(recorder.events_table_name, "public.testcase_events")
        self.assertEqual(recorder.tracking_table_name, "public.testcase_tracking")


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecorderTestCase
del InfrastructureFactoryTestCase
del SetupPostgresDatastore
del WithSchema
del TestConnectionPool
