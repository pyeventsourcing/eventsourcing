import os
from time import sleep
from unittest import TestCase
from uuid import uuid4

import psycopg2
from psycopg2.errorcodes import UNDEFINED_TABLE

from eventsourcing.persistence import (
    InfrastructureFactory,
    OperationalError,
    StoredEvent,
)
from eventsourcing.postgres import (
    Factory,
    PostgresAggregateRecorder,
    PostgresApplicationRecorder,
    PostgresDatastore,
    PostgresProcessRecorder,
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


class TestPostgresDatastore(TestCase):
    def test_transaction(self):
        datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )

        # Get a transaction.
        transaction = datastore.transaction()

        # Check connection is not idle.
        self.assertFalse(transaction.c.is_idle.is_set())

        # Check transaction gives database cursor when used as context manager.
        with transaction as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchall(), [[1]])

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
        transaction = datastore.transaction()

        # Check connection is not idle.
        conn = transaction.c
        self.assertFalse(conn.is_idle.is_set())

        # Delete the transaction context manager before entering.
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
        with datastore.transaction() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchall(), [[1]])

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
        transaction = datastore.transaction()
        with transaction as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchall(), [[1]])

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

        # Check closed connection can be replaced and also closed.
        transaction = datastore.transaction()
        with transaction as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchall(), [[1]])

        self.assertTrue(transaction.c.is_closing.wait(timeout=0.5))
        for _ in range(1000):
            if transaction.c.is_closed:
                break
            else:
                sleep(0.0001)
        else:
            self.fail("Connection is not closed")


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

    def test_raises_operational_error_when_creating_table_fails(self):
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        recorder.create_table_statements = ["BLAH"]
        with self.assertRaises(OperationalError):
            recorder.create_table()

    def test_raises_operational_error_when_inserting_fails(self):
        # Construct the recorder.
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()

        # Mess up the statement.
        recorder.insert_events_statement = "BLAH"

        # Write two stored events.
        originator_id = uuid4()

        stored_event1 = StoredEvent(
            originator_id=originator_id,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        with self.assertRaises(OperationalError):
            recorder.insert_events([stored_event1])

    def test_raises_operational_error_when_selecting_fails(self):
        # Construct the recorder.
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )

        originator_id = uuid4()
        with self.assertRaises(OperationalError):
            recorder.select_events(originator_id=originator_id)


class TestPostgresApplicationRecorder(ApplicationRecorderTestCase):
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
        recorder = PostgresApplicationRecorder(
            self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def close_db_connection(self, *args):
        self.datastore.close_connection()

    def test_raises_operational_error_when_selecting_fails(self):
        # Construct the recorder.
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )

        with self.assertRaises(OperationalError):
            recorder.select_notifications(start=1, limit=1)

        with self.assertRaises(OperationalError):
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

    def test_raises_operational_error_when_selecting_fails(self):
        # Construct the recorder.
        recorder = PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
            tracking_table_name="notification_tracking",
        )

        with self.assertRaises(OperationalError):
            recorder.max_tracking_id("application name")


class TestPostgresInfrastructureFactory(InfrastructureFactoryTestCase):
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
        if Factory.POSTGRES_CONN_MAX_AGE in os.environ:
            del os.environ[Factory.POSTGRES_CONN_MAX_AGE]
        super().tearDown()

    def test_conn_max_age_is_set_to_empty_string(self):
        os.environ[Factory.POSTGRES_CONN_MAX_AGE] = ""
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.conn_max_age, None)

    def test_conn_max_age_is_set_to_number(self):
        os.environ[Factory.POSTGRES_CONN_MAX_AGE] = "0"
        self.factory = Factory("TestCase", os.environ)
        self.assertEqual(self.factory.datastore.conn_max_age, 0)

    def test_environment_error_raised_when_conn_max_age_not_a_float(self):
        os.environ[Factory.POSTGRES_CONN_MAX_AGE] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = Factory("TestCase", os.environ)
        self.assertEqual(
            cm.exception.args[0],
            "Postgres environment value for key 'POSTGRES_CONN_MAX_AGE' "
            "is invalid. If set, a float or empty string is expected: 'abc'",
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
        with datastore.transaction() as c:
            statement = f"DROP TABLE {table_name};"
            c.execute(statement)
    except psycopg2.errors.lookup(UNDEFINED_TABLE):
        pass
