import os
from time import sleep
from unittest import TestCase
from unittest.mock import Mock
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
    Connection,
    Factory,
    PostgresAggregateRecorder,
    PostgresApplicationRecorder,
    PostgresDatastore,
    PostgresProcessRecorder,
    Transaction,
)
from eventsourcing.tests.aggregaterecorder_testcase import (
    AggregateRecorderTestCase,
)
from eventsourcing.tests.applicationrecorder_testcase import (
    ApplicationRecorderTestCase,
)
from eventsourcing.tests.infrastructure_testcases import (
    InfrastructureFactoryTestCase,
)
from eventsourcing.tests.processrecorder_testcase import (
    ProcessRecorderTestCase,
)
from eventsourcing.utils import get_topic


def pg_close_all_connections(
    name="eventsourcing",
    host="127.0.0.1",
    port="5432",
    user="postgres",
    password="postgres",
):
    try:
        # For local development... probably.
        pg_conn = psycopg2.connect(
            dbname=name,
            host=host,
            port=port,
        )
    except psycopg2.Error:
        # For GitHub actions.
        """CREATE ROLE postgres LOGIN SUPERUSER PASSWORD 'postgres';"""
        pg_conn = psycopg2.connect(
            dbname=name,
            host=host,
            port=port,
            user=user,
            password=password,
        )
    close_all_connections = """
    SELECT
        pg_terminate_backend(pid)
    FROM
        pg_stat_activity
    WHERE
        -- don't kill my own connection!
        pid <> pg_backend_pid();

    """
    pg_conn_cursor = pg_conn.cursor()
    pg_conn_cursor.execute(close_all_connections)
    return close_all_connections, pg_conn_cursor


class TestTransaction(TestCase):
    def setUp(self) -> None:
        self.mock = Mock(Connection(Mock(connection), max_age=None))
        self.t = Transaction(self.mock, commit=True)

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
    def test_connect_failure_raises_interface_error(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="9876543210",  # bad port
            user="eventsourcing",
            password="eventsourcing",
        )
        with self.assertRaises(InterfaceError):
            datastore.transaction(commit=True)

    def test_transaction(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )

        # Get a transaction.
        transaction = datastore.transaction(commit=False)

        # Check connection is not idle.
        self.assertFalse(transaction.c.is_idle.is_set())

        # Check transaction gives database cursor when used as context manager.
        with transaction as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                self.assertEqual(c.fetchall(), [[1]])

        # Check connection is idle after context manager has exited.
        self.assertTrue(transaction.c.is_idle.wait(timeout=0.1))

    def test_connection_of_transaction_not_used_as_context_manager_also_goes_idle(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )

        # Get a transaction.
        transaction = datastore.transaction(commit=False)

        # Check connection is not idle.
        conn = transaction.c
        self.assertFalse(conn.is_idle.is_set())

        # Delete the transaction context manager before entering.
        print("Testing transaction not used as context manager, expecting exception...")
        del transaction

        # Check connection is idle after garbage collection.
        self.assertTrue(conn.is_idle.wait(timeout=0.1))

    def test_close_connection(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        # Try closing without first creating connection.
        datastore.close_connection()

        # Create a connection.
        with datastore.transaction(commit=False) as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                self.assertEqual(c.fetchall(), [[1]])

        # Try closing after creating connection.
        datastore.close_connection()

    def test_timer_closes_connection(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
            conn_max_age=0,
        )

        # Check connection is closed after using transaction.
        transaction = datastore.transaction(commit=False)
        with transaction as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                self.assertEqual(c.fetchall(), [[1]])

        self.assertTrue(transaction.c.is_closing.wait(timeout=0.5))
        for _ in range(1000):
            if transaction.c.is_closed:
                break
            else:
                sleep(0.0001)
        else:
            self.fail("Connection is not closed")

        with self.assertRaises(psycopg2.InterfaceError) as cm:
            transaction.c.cursor()
        self.assertEqual(cm.exception.args[0], "connection already closed")

        # Check closed connection can be recreated and also closed.
        transaction = datastore.transaction(commit=False)
        with transaction as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                self.assertEqual(c.fetchall(), [[1]])

        self.assertTrue(transaction.c.is_closing.wait(timeout=0.5))
        for _ in range(1000):
            if transaction.c.is_closed:
                break
            else:
                sleep(0.0001)
        else:
            self.fail("Connection is not closed")

    def test_pre_ping(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
            pre_ping=True,
        )

        # Create a connection.
        transaction = datastore.transaction(commit=False)
        pg_conn = transaction.c.c
        self.assertEqual(pg_conn, transaction.c.c)

        # Check the connection works.
        with transaction as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                self.assertEqual(c.fetchall(), [[1]])

        # Close all connections via separate connection.
        pg_close_all_connections()

        # Check the connection doesn't think it's closed.
        self.assertFalse(transaction.c.is_closed)

        # Check we can get a new connection that works.
        transaction = datastore.transaction(commit=False)
        with transaction as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                self.assertEqual(c.fetchall(), [[1]])

        # Check it's actually a different connection.
        self.assertNotEqual(pg_conn, transaction.c.c)

        # Check this doesn't work if we don't use pre_ping.
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
            pre_ping=False,
        )

        # Create a connection.
        transaction = datastore.transaction(commit=False)
        pg_conn = transaction.c.c
        self.assertEqual(pg_conn, transaction.c.c)

        # Check the connection works.
        with transaction as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                self.assertEqual(c.fetchall(), [[1]])

        # Close all connections via separate connection.
        pg_close_all_connections()

        # Check the connection doesn't think it's closed.
        self.assertFalse(transaction.c.is_closed)

        # Get a stale connection and check it doesn't work.
        transaction = datastore.transaction(commit=False)

        # Check it's the same connection.
        self.assertEqual(pg_conn, transaction.c.c)
        with self.assertRaises(InterfaceError):
            with transaction as conn:
                with conn.cursor() as c:
                    c.execute("SELECT 1")


class TestPostgresAggregateRecorder(AggregateRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        drop_postgres_table(self.datastore, "stored_events")

    def create_recorder(self):
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()

    def test_insert_and_select(self):
        super().test_insert_and_select()

    def test_retry_insert_events_after_closing_connection(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Check we have a connection (from create_table).
        self.assertTrue(self.datastore._connections)

        # Close connections.
        pg_close_all_connections()

        # Write a stored event.
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        recorder.insert_events([stored_event1])

    def test_retry_select_events_after_closing_connection(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Check we have a connection (from create_table).
        self.assertTrue(self.datastore._connections)

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

        # Select events.
        recorder.select_events(originator_id)


class TestPostgresAggregateRecorderErrors(TestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")

    def create_recorder(self):
        return PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )

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

        # Create the table.
        recorder.create_table()

        # Check the statement is not prepared.
        statement_name = "select_stored_events"
        conn = self.datastore.get_connection()
        self.assertFalse(conn.is_prepared.get(statement_name))

        # Cause the statement to be prepared.
        recorder.select_events(originator_id=uuid4())

        # Check the statement was prepared.
        conn = self.datastore.get_connection()
        self.assertTrue(conn.is_prepared.get(statement_name))

        # Forget the statement is prepared.
        del conn.is_prepared[statement_name]

        # Should ignore "duplicate prepared statement" error.
        recorder.select_events(originator_id=uuid4())

        # Check the statement was prepared.
        conn = self.datastore.get_connection()
        self.assertTrue(conn.is_prepared.get(statement_name))


class TestPostgresApplicationRecorder(ApplicationRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")

    def create_recorder(self):
        recorder = PostgresApplicationRecorder(
            self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def close_db_connection(self, *args):
        self.datastore.close_connection()

    def test_concurrent_no_conflicts(self):
        super().test_concurrent_no_conflicts()

    def test_concurrent_throughput(self):
        super().test_concurrent_throughput()

    def test_retry_select_notifications_after_closing_connection(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Check we have a connection (from create_table).
        self.assertTrue(self.datastore._connections)

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

        # Select events.
        recorder.select_notifications(start=1, limit=1)

    def test_retry_max_notification_id_after_closing_connection(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Check we have a connection (from create_table).
        self.assertTrue(self.datastore._connections)

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

        # Select events.
        recorder.max_notification_id()


class TestPostgresApplicationRecorderErrors(TestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")

    def create_recorder(self):
        return PostgresApplicationRecorder(
            self.datastore, events_table_name="stored_events"
        )

    def test_select_notification_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Select notifications without creating table.
        with self.assertRaises(ProgrammingError):
            recorder.select_notifications(start=1, limit=1)

    def test_select_notification_raises_programming_error_when_sql_is_broken(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Create table.
        recorder.create_table()

        # Select notifications with broken statement.
        recorder.select_notifications_statement = "BLAH"
        with self.assertRaises(ProgrammingError):
            recorder.select_notifications(start=1, limit=1)

    def test_max_notification_id_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )

        # Select notifications without creating table.
        with self.assertRaises(ProgrammingError):
            recorder.max_notification_id()

    def test_max_notification_id_raises_programming_error_when_sql_is_broken(self):
        # Construct the recorder.
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )

        # Create table.
        recorder.create_table()

        # Select notifications with broken statement.
        recorder.max_notification_id_statement = "BLAH"
        with self.assertRaises(ProgrammingError):
            recorder.max_notification_id()


class TestPostgresProcessRecorder(ProcessRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")
        drop_postgres_table(self.datastore, "notification_tracking")

    def create_recorder(self):
        recorder = PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
            tracking_table_name="notification_tracking",
        )
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()

    def test_retry_max_tracking_id_after_closing_connection(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Check we have a connection (from create_table).
        self.assertTrue(self.datastore._connections)

        # Write a stored event.
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

        # Select events.
        notification_id = recorder.max_tracking_id("upstream")
        self.assertEqual(notification_id, 1)


class TestPostgresProcessRecorderErrors(TestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")
        drop_postgres_table(self.datastore, "notification_tracking")

    def create_recorder(self):
        return PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
            tracking_table_name="notification_tracking",
        )

    def test_max_tracking_id_raises_programming_error_when_table_not_created(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Get max tracking ID without creating table.
        with self.assertRaises(ProgrammingError):
            recorder.max_tracking_id("upstream")

    def test_max_tracking_id_raises_programming_error_when_sql_is_broken(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Create table.
        recorder.create_table()

        # Mess up the SQL statement.
        recorder.max_tracking_id_statement = "BLAH"

        # Get max tracking ID with broken statement.
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
        os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
        os.environ[Factory.POSTGRES_DBNAME] = "eventsourcing"
        os.environ[Factory.POSTGRES_HOST] = "127.0.0.1"
        os.environ[Factory.POSTGRES_PORT] = "5432"
        os.environ[Factory.POSTGRES_USER] = "eventsourcing"
        os.environ[Factory.POSTGRES_PASSWORD] = "eventsourcing"
        if Factory.POSTGRES_CONN_MAX_AGE in os.environ:
            del os.environ[Factory.POSTGRES_CONN_MAX_AGE]
        if Factory.POSTGRES_PRE_PING in os.environ:
            del os.environ[Factory.POSTGRES_PRE_PING]
        if Factory.POSTGRES_LOCK_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_LOCK_TIMEOUT]
        if Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT]
        self.drop_tables()
        super().setUp()

    def tearDown(self) -> None:
        self.drop_tables()
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
        if Factory.POSTGRES_CONN_MAX_AGE in os.environ:
            del os.environ[Factory.POSTGRES_CONN_MAX_AGE]
        if Factory.POSTGRES_PRE_PING in os.environ:
            del os.environ[Factory.POSTGRES_PRE_PING]
        if Factory.POSTGRES_LOCK_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_LOCK_TIMEOUT]
        if Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT in os.environ:
            del os.environ[Factory.POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT]
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
        os.environ[Factory.POSTGRES_CONN_MAX_AGE] = ""
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.conn_max_age, None)

    def test_conn_max_age_is_set_to_number(self):
        os.environ[Factory.POSTGRES_CONN_MAX_AGE] = "0"
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.conn_max_age, 0)

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

    def test_pre_ping_off_by_default(self):
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.pre_ping, False)

    def test_pre_ping_off(self):
        os.environ[Factory.POSTGRES_PRE_PING] = "off"
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.pre_ping, False)

    def test_pre_ping_on(self):
        os.environ[Factory.POSTGRES_PRE_PING] = "on"
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.pre_ping, True)

    def test_environment_error_raised_when_conn_max_age_not_a_float(self):
        os.environ[Factory.POSTGRES_CONN_MAX_AGE] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory("TestCase", os.environ)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_CONN_MAX_AGE' "
            "is invalid. If set, a float or empty string is expected: 'abc'",
        )

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


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecorderTestCase
del InfrastructureFactoryTestCase


def drop_postgres_table(datastore: PostgresDatastore, table_name):
    try:
        with datastore.transaction(commit=True) as t:
            statement = f"DROP TABLE {table_name};"
            with t.c.cursor() as c:
                c.execute(statement)
    except PersistenceError:
        pass
