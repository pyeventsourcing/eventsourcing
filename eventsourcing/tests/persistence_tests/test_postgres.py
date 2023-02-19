from threading import Event, Thread
from time import sleep
from unittest import TestCase
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import psycopg2
from psycopg2.extensions import connection

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
    def test_commit_calls_commit(self):
        mock = MagicMock(connection)
        conn = PostgresConnection(pg_conn=mock, max_age=1)
        conn.commit()
        mock.commit.assert_called_once()

    def test_rollback_calls_rollback(self):
        mock = MagicMock(connection)
        conn = PostgresConnection(pg_conn=mock, max_age=1)
        conn.rollback()
        mock.rollback.assert_called_once()

    def test_transaction_context_manager(self):
        pg_conn = psycopg2.connect(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
            connect_timeout=5,
        )
        conn = PostgresConnection(pg_conn=pg_conn, max_age=1)
        with conn.transaction(commit=False) as curs:
            self.assertIsInstance(curs, PostgresCursor)
            curs.execute("SELECT 1")
            self.assertEqual(curs.fetchall(), [[1]])

        with self.assertRaises(ProgrammingError):
            with conn.transaction(commit=False) as curs:
                curs.execute("BLAH")


class TestPostgresConnectionPool(TestConnectionPool):
    ProgrammingError = psycopg2.ProgrammingError
    PersistenceError = psycopg2.Error
    allowed_connecting_time = 0.02

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


class TestTransaction(TestCase):
    def setUp(self) -> None:
        self.mock = MagicMock(PostgresConnection(MagicMock(connection), max_age=None))
        self.t = PostgresTransaction(self.mock, commit=True)

    def test_calls_commit_if_error_not_raised_during_transaction(self):
        with self.t:
            pass
        self.mock.commit.assert_called()
        self.mock.rollback.assert_not_called()
        self.mock.close.assert_not_called()

    def test_calls_rollback_if_error_is_raised_during_transaction(self):
        with self.assertRaises(TypeError):
            with self.t:
                raise TypeError
        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()
        self.mock.close.assert_not_called()

    def test_calls_rollback_if_commit_arg_is_false(self):
        # Avoid traceback error from Transaction.__del__.
        self.t.has_entered = True
        # Create transaction with commit=False.
        self.t = PostgresTransaction(self.mock, commit=False)
        with self.t:
            pass
        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()
        self.mock.close.assert_not_called()

    def test_calls_close_if_interface_error_is_raised_during_transaction(self):
        with self.assertRaises(InterfaceError):
            with self.t:
                self.raise_interface_error()
        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()
        self.mock.close.assert_called()

    def test_calls_close_if_interface_error_is_raised_during_commit(self):
        self.mock.commit = Mock(
            side_effect=self.raise_interface_error, name="mock commit method"
        )
        with self.assertRaises(InterfaceError):
            with self.t:
                pass
        self.mock.commit.assert_called()
        self.mock.rollback.assert_not_called()
        self.mock.close.assert_called()

    def test_does_not_call_close_if_data_error_is_raised_during_commit(self):
        self.mock.commit = Mock(
            side_effect=self.raise_data_error, name="mock commit method"
        )
        with self.assertRaises(DataError):
            with self.t:
                pass
        self.mock.commit.assert_called()
        self.mock.rollback.assert_not_called()
        self.mock.close.assert_not_called()

    def test_calls_close_if_interface_error_is_raised_during_rollback(self):
        self.mock.rollback = Mock(
            side_effect=self.raise_interface_error, name="mock rollback method"
        )
        with self.assertRaises(InterfaceError):
            with self.t:
                raise psycopg2.Error

        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()
        self.mock.close.assert_called()

    def test_does_not_call_close_if_data_error_is_raised_during_rollback(self):
        self.mock.rollback = Mock(
            side_effect=self.raise_data_error, name="mock rollback method"
        )
        with self.assertRaises(DataError):
            with self.t:
                raise psycopg2.Error

        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()
        self.mock.close.assert_not_called()

    def raise_interface_error(self):
        raise psycopg2.InterfaceError()

    def raise_data_error(self):
        raise psycopg2.DataError()

    def test_converts_errors_raised_in_transactions(self):
        errors = [
            (InterfaceError, psycopg2.InterfaceError),
            (DataError, psycopg2.DataError),
            (OperationalError, psycopg2.OperationalError),
            (IntegrityError, psycopg2.IntegrityError),
            (InternalError, psycopg2.InternalError),
            (ProgrammingError, psycopg2.ProgrammingError),
            (NotSupportedError, psycopg2.NotSupportedError),
            (DatabaseError, psycopg2.DatabaseError),
            (PersistenceError, psycopg2.Error),
        ]
        for es_err, psy_err in errors:
            with self.assertRaises(es_err):
                with self.t:
                    raise psy_err

        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()
        self.mock.close.assert_called()


class TestPostgresDatastore(TestCase):
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

    def test_transactions_from_connection(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        # By getting transaction from connection, we can do several transactions.
        with datastore.get_connection() as conn:
            # Transaction 1.
            with conn.transaction(commit=False) as curs:
                curs.execute("SELECT 1")
                self.assertEqual(curs.fetchall(), [[1]])

            # Transaction 2.
            with conn.transaction(commit=True) as curs:
                curs.execute("SELECT 1")
                self.assertEqual(curs.fetchall(), [[1]])

            # Transaction 3.
            with conn.transaction(commit=False) as curs:
                curs.execute("SELECT 1")
                self.assertEqual(curs.fetchall(), [[1]])

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
            self.assertEqual(curs.fetchall(), [[1]])

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
                    self.assertEqual(curs.fetchall(), [[1]])

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
        with self.assertRaises(psycopg2.Error):
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

    def test_report_on_prepared_statements(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
            pre_ping=True,
        )
        pg, py = datastore.report_on_prepared_statements()
        self.assertEqual(pg, [])
        self.assertEqual(py, [])


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

    def test_get_statement_name_alias(self):
        # A statement name that is not too long is aliased to the same.
        recorder = self.create_recorder(table_name="stored_events")
        alias = recorder.get_statement_alias(recorder.insert_events_statement_name)
        self.assertEqual(alias, recorder.insert_events_statement_name)

        # A statement name that is too long is aliased to something else.
        recorder = self.create_recorder(table_name=EVENTS_TABLE_NAME)
        alias = recorder.get_statement_alias(recorder.insert_events_statement_name)
        self.assertNotEqual(alias, recorder.insert_events_statement_name)

    def test_insert_and_select(self):
        super().test_insert_and_select()

    def test_performance(self):
        super().test_performance()

    def test_report_on_prepared_statements(self):
        # Shouldn't be any prepared statements, because haven't done anything.
        recorder = self.create_recorder()
        self.datastore.pool.pool_size = 1
        pg, py = recorder.datastore.report_on_prepared_statements()
        self.assertEqual(pg, [])
        self.assertEqual(py, [])

        # After selecting by ID, should have prepared 'select_stored_events'.
        recorder.select_events(uuid4())
        pg, py = recorder.datastore.report_on_prepared_statements()
        if self.schema:
            qualified_table_name = f"{self.schema}.{EVENTS_TABLE_NAME}"
        else:
            qualified_table_name = f"{EVENTS_TABLE_NAME}"
        select_statement_name = f"select_{qualified_table_name.replace('.', '_')}"
        select_alias = recorder.statement_name_aliases[select_statement_name]
        self.assertEqual(len(pg), 1)
        self.assertEqual(len(py), 1)
        self.assertEqual(pg[0][0], select_alias)
        self.assertEqual(
            pg[0][1],
            (
                f"PREPARE {select_alias} AS SELECT * FROM "
                f"{qualified_table_name} WHERE originator_id = $1 ORDER "
                "BY originator_version ASC"
            ),
        )
        self.assertEqual(pg[0][3], "{uuid}")
        self.assertEqual(pg[0][4], True)
        self.assertEqual(py, [select_statement_name])

        # Check prepared 'select_stored_events_desc_limit'.
        recorder.select_events(uuid4(), desc=True, limit=1)
        pg, py = recorder.datastore.report_on_prepared_statements()
        self.assertEqual(len(pg), 2)
        self.assertEqual(len(py), 2)
        select_desc_limit_statement_name = (
            f"select_{qualified_table_name.replace('.', '_')}_desc_limit"
        )
        self.assertEqual(
            pg[0][0],
            recorder.statement_name_aliases[select_desc_limit_statement_name],
        )
        self.assertEqual(
            pg[1][0], recorder.statement_name_aliases[select_statement_name]
        )

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

    def test_retry_insert_events_after_deallocating_prepared_statement(self):
        # This checks connection is recreated after OperationalError.

        # Construct the recorder.
        recorder = self.create_recorder()
        self.datastore.pool.pool_size = 1

        # Write a stored event.
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        recorder.insert_events([stored_event1])

        # Deallocate the prepared insert statement.
        self.assertTrue(self.datastore.pool._pool)
        with self.datastore.get_connection() as conn:
            statement_name = recorder.insert_events_statement_name
            self.assertIn(statement_name, conn.is_prepared)
            conn.cursor().execute(
                f"DEALLOCATE " f"{recorder.statement_name_aliases[statement_name]}"
            )

        # Write a stored event.
        stored_event2 = StoredEvent(
            originator_id=uuid4(),
            originator_version=1,
            topic="topic2",
            state=b"state2",
        )
        recorder.insert_events([stored_event2])

    def test_retry_select_events_after_closing_connection(self):
        # This checks connection is recreated after being closed on the server.

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
        recorder.select_events(originator_id)

    def test_retry_select_events_after_deallocating_prepared_statement(self):
        # This checks connection is recreated after OperationalError.

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

        # Select events.
        recorder.select_events(originator_id)

        # Deallocate the prepared select statement.
        with self.datastore.get_connection() as conn:
            if self.schema:
                statement_name = f"select_{self.schema}_{EVENTS_TABLE_NAME}"
            else:
                statement_name = f"select_{EVENTS_TABLE_NAME}"
            self.assertIn(statement_name, conn.is_prepared)
            conn.cursor().execute(
                f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
            )

        # Select events.
        recorder.select_events(originator_id)


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

    def test_duplicate_prepared_statement_error_is_ignored(self):
        # Construct the recorder.
        recorder = self.create_recorder()
        self.datastore.pool.pool_size = 1

        # Create the table.
        recorder.create_table()

        # Check the statement is not prepared.
        statement_name = f"select_{EVENTS_TABLE_NAME}"
        with self.datastore.get_connection() as conn:
            self.assertNotIn(statement_name, conn.is_prepared)

        # Cause the statement to be prepared.
        recorder.select_events(originator_id=uuid4())

        # Check the statement was prepared.
        with self.datastore.get_connection() as conn:
            self.assertIn(statement_name, conn.is_prepared)

            # Forget the statement is prepared.
            conn.is_prepared.remove(statement_name)

        # Should ignore "duplicate prepared statement" error.
        recorder.select_events(originator_id=uuid4())

        # Check the statement was prepared.
        with self.datastore.get_connection() as conn:
            self.assertIn(statement_name, conn.is_prepared)


class TestPostgresApplicationRecorder(
    SetupPostgresDatastore, ApplicationRecorderTestCase
):
    def create_recorder(self, table_name=EVENTS_TABLE_NAME):
        if self.datastore.schema:
            table_name = f"{self.datastore.schema}.{table_name}"
        recorder = PostgresApplicationRecorder(
            self.datastore, events_table_name=table_name
        )
        recorder.create_table()
        return recorder

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

    def test_retry_select_notifications_after_deallocating_prepared_statement(self):
        # This checks connection is recreated after OperationalError.

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

        # Select notifications.
        recorder.select_notifications(start=1, limit=1)

        # Deallocate prepared statement.
        self.assertTrue(self.datastore.pool._pool)
        with self.datastore.get_connection() as conn:
            statement_name = (
                f"select_notifications_{recorder.events_table_name}".replace(".", "_")
            )
            self.assertIn(statement_name, conn.is_prepared)
            conn.cursor().execute(
                f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
            )

        # Select notifications.
        recorder.select_notifications(start=1, limit=1)

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

    def test_retry_max_notification_id_after_deallocating_prepared_statement(self):
        # This checks connection is recreated after OperationalError.

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

        # Get max notification ID.
        recorder.max_notification_id()

        # Deallocate prepared statement.
        self.assertTrue(self.datastore.pool._pool)
        if self.schema:
            qualified_table_name = f"{self.schema}.{EVENTS_TABLE_NAME}"
        else:
            qualified_table_name = f"{EVENTS_TABLE_NAME}"
        statement_name = f"max_notification_id_{qualified_table_name}".replace(".", "_")
        for conn in self.datastore.pool._pool:
            self.assertIn(statement_name, conn.is_prepared)
            conn.cursor().execute(
                f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
            )

        # Get max notification ID.
        recorder.max_notification_id()

    def test_prepare_lock_timeout_actually_works(self):
        self.datastore.lock_timeout = 1
        recorder = self.create_recorder()

        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=1,
            topic="topic1",
            state=b"state1",
        )

        table_lock_acquired = Event()
        stalling_event = Event()
        lock_timeout_happened = Event()

        def insert1():
            with self.datastore.get_connection() as conn:
                recorder._prepare_insert_events(conn)
                with conn.transaction(commit=True) as curs:
                    recorder._insert_events(curs, [stored_event1])
                    table_lock_acquired.set()
                    stalling_event.wait(timeout=10)  # keep the lock

        def insert2():
            if not table_lock_acquired.wait(timeout=1):
                return
            try:
                with self.datastore.get_connection() as conn:
                    # This should timeout, because table is locked.
                    recorder._prepare_insert_events(conn)
            except Exception:
                lock_timeout_happened.set()
                stalling_event.set()

        thread1 = Thread(target=insert1, daemon=True)
        thread1.start()
        thread2 = Thread(target=insert2, daemon=True)
        thread2.start()

        self.assertTrue(table_lock_acquired.wait(timeout=1))
        lock_timeout_happened.wait(timeout=4)
        stalling_event.set()
        self.assertTrue(lock_timeout_happened.is_set())

        thread1.join(timeout=5)
        thread2.join(timeout=5)

    def test_insert_lock_timeout_actually_works(self):
        self.datastore.lock_timeout = 1
        recorder = self.create_recorder()

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

        has_2_prepared = Event()
        table_lock_acquired = Event()
        stalling_event = Event()
        lock_timeout_happened = Event()

        def insert1():
            with self.datastore.get_connection() as conn:
                # Wait until prepared, otherwise we can't test insert lock.
                has_2_prepared.wait(timeout=10)
                recorder._prepare_insert_events(conn)
                with conn.transaction(commit=True) as curs:
                    recorder._insert_events(curs, [stored_event1])
                    table_lock_acquired.set()
                    stalling_event.wait(timeout=10)  # keep the lock

        def insert2():
            try:
                with self.datastore.get_connection() as conn:
                    recorder._prepare_insert_events(conn)
                    has_2_prepared.set()
                    table_lock_acquired.wait(timeout=10)
                    with conn.transaction(commit=True) as curs:
                        recorder._insert_events(curs, [stored_event2])
            except Exception:
                lock_timeout_happened.set()
                stalling_event.set()

        thread1 = Thread(target=insert1, daemon=True)
        thread1.start()
        thread2 = Thread(target=insert2, daemon=True)
        thread2.start()

        lock_timeout_happened.wait(timeout=4)
        stalling_event.set()
        self.assertTrue(lock_timeout_happened.is_set())

        thread1.join(timeout=5)
        thread2.join(timeout=5)


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

    def test_retry_max_tracking_id_after_deallocating_prepared_statement(self):
        # This checks connection is recreated after OperationalError.

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

        # Get max tracking ID.
        notification_id = recorder.max_tracking_id("upstream")
        self.assertEqual(notification_id, 1)

        # Deallocate prepared statement.
        self.assertTrue(self.datastore.pool._pool)
        with self.datastore.get_connection() as conn:
            statement_name = recorder.max_tracking_id_statement_name
            self.assertIn(statement_name, conn.is_prepared)
            conn.cursor().execute(
                f"DEALLOCATE {recorder.statement_name_aliases[statement_name]}"
            )

        # Get max tracking ID.
        notification_id = recorder.max_tracking_id("upstream")
        self.assertEqual(notification_id, 1)


class TestPostgresProcessRecorderWitSchema(WithSchema, TestPostgresProcessRecorder):
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
            self.factory = Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_CONN_MAX_AGE' "
            "is invalid. If set, a float or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_connect_timeout_not_an_integer(self):
        self.env[Factory.POSTGRES_CONNECT_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_CONNECT_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_pool_timeout_not_an_integer(self):
        self.env[Factory.POSTGRES_POOL_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_POOL_TIMEOUT' "
            "is invalid. If set, a float or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_lock_timeout_not_an_integer(self):
        self.env[Factory.POSTGRES_LOCK_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_LOCK_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_min_conn_not_an_integer(self):
        self.env[Factory.POSTGRES_POOL_SIZE] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_POOL_SIZE' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_max_conn_not_an_integer(self):
        self.env[Factory.POSTGRES_POOL_MAX_OVERFLOW] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory(self.env)
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
            self.factory = Factory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key "
            "'POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT' "
            "is invalid. If set, an integer or empty string is expected: 'abc'",
        )

    def test_environment_error_raised_when_dbname_missing(self):
        del self.env[Factory.POSTGRES_DBNAME]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres database name not found in environment "
            "with key 'POSTGRES_DBNAME'",
        )

    def test_environment_error_raised_when_dbhost_missing(self):
        del self.env[Factory.POSTGRES_HOST]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres host not found in environment with key 'POSTGRES_HOST'",
        )

    def test_environment_error_raised_when_user_missing(self):
        del self.env[Factory.POSTGRES_USER]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres user not found in environment with key 'POSTGRES_USER'",
        )

    def test_environment_error_raised_when_password_missing(self):
        del self.env[Factory.POSTGRES_PASSWORD]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct(self.env)
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
