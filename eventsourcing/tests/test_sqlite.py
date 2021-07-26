import os
from unittest import TestCase
from uuid import uuid4

from eventsourcing.persistence import InfrastructureFactory, OperationalError
from eventsourcing.sqlite import (
    Factory,
    SQLiteAggregateRecorder,
    SQLiteApplicationRecorder,
    SQLiteDatastore,
    SQLiteProcessRecorder,
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
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.utils import get_topic


class TestSqliteDatastore(TestCase):
    def setUp(self) -> None:
        self.datastore = SQLiteDatastore(":memory:")

    def test_get_connection(self):
        connection = self.datastore.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 1)
        self.assertEqual(rows[0][0], 1)

    def test_get_cursor(self):
        cursor = self.datastore.get_cursor()
        cursor.execute("SELECT 1")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 1)
        self.assertEqual(rows[0][0], 1)

    def test_transaction(self):
        transaction = self.datastore.transaction()
        self.assertEqual(transaction.c, self.datastore.get_connection())

    def test_close_connection(self):
        # Try closing without opening.
        self.datastore.close_connection()

        # Try closing after opening.
        self.datastore.get_connection()
        self.datastore.close_connection()


class TestSQLiteAggregateRecorder(AggregateRecorderTestCase):
    def create_recorder(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        return recorder


class TestSQLiteRecorderErrors(TestCase):
    def test_raises_operational_error_when_creating_table_fails(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        recorder.create_table_statements = ["BLAH"]
        with self.assertRaises(OperationalError):
            recorder.create_table()

    def test_raises_operational_error_when_inserting_fails(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.insert_events([])

    def test_raises_operational_error_when_selecting_fails(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.select_events(uuid4())


class TestSQLiteApplicationRecorder(ApplicationRecorderTestCase):
    def test_insert_select(self):
        self.db_uri = ":memory:"
        super().test_insert_select()

    def test_concurrent_no_conflicts(self):
        # db_uri = "file::memory:?cache=shared"
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_insert_select()

    def create_recorder(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(self.db_uri))
        recorder.create_table()
        return recorder

    def test_raises_operational_error_when_inserting_fails(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            # Haven't created table.
            recorder.insert_events([])

    def test_raises_operational_error_when_selecting_fails(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            # Haven't created table.
            recorder.select_events(uuid4())

        with self.assertRaises(OperationalError):
            # Haven't created table.
            recorder.select_notifications(start=1, limit=1)

        with self.assertRaises(OperationalError):
            # Haven't created table.
            recorder.max_notification_id()


class TestSQLiteProcessRecorder(ProcessRecorderTestCase):
    def create_recorder(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        return recorder

    def test_raises_operational_error_when_inserting_fails(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.insert_events([])

    def test_raises_operational_error_when_selecting_fails(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.select_events(uuid4())

        with self.assertRaises(OperationalError):
            recorder.max_tracking_id("application name")


class TestSQLiteInfrastructureFactory(InfrastructureFactoryTestCase):
    def expected_factory_class(self):
        return Factory

    def expected_aggregate_recorder_class(self):
        return SQLiteAggregateRecorder

    def expected_application_recorder_class(self):
        return SQLiteApplicationRecorder

    def expected_process_recorder_class(self):
        return SQLiteProcessRecorder

    def setUp(self) -> None:
        os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
        os.environ[Factory.SQLITE_DBNAME] = ":memory:"
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        if Factory.SQLITE_DBNAME in os.environ:
            del os.environ[Factory.SQLITE_DBNAME]

    def test_environment_error_raised_when_dbname_missing(self):
        del os.environ[Factory.SQLITE_DBNAME]
        with self.assertRaises(EnvironmentError) as cm:
            self.factory = InfrastructureFactory.construct("TestCase")
        self.assertEqual(
            cm.exception.args[0],
            "SQLite database name not found in environment with key 'SQLITE_DBNAME'",
        )


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecorderTestCase
del InfrastructureFactoryTestCase
