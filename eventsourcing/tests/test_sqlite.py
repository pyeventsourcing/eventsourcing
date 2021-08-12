import os
import sqlite3
from sqlite3 import Connection
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4

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
)
from eventsourcing.sqlite import (
    Factory,
    SQLiteAggregateRecorder,
    SQLiteApplicationRecorder,
    SQLiteDatastore,
    SQLiteProcessRecorder,
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
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.utils import get_topic


class TestTransaction(TestCase):
    def setUp(self) -> None:
        self.mock = Mock(Connection)
        self.t = Transaction(self.mock, commit=True)

    def test_calls_commit_if_error_not_raised_during_transaction(self):
        with self.t:
            pass
        self.mock.commit.assert_called()
        self.mock.rollback.assert_not_called()

    def test_calls_rollback_if_error_is_raised_during_transaction(self):
        with self.assertRaises(TypeError):
            with self.t:
                raise TypeError
        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()

    def test_converts_errors_raised_in_transactions(self):
        errors = [
            (InterfaceError, sqlite3.InterfaceError),
            (DataError, sqlite3.DataError),
            (OperationalError, sqlite3.OperationalError),
            (IntegrityError, sqlite3.IntegrityError),
            (InternalError, sqlite3.InternalError),
            (ProgrammingError, sqlite3.ProgrammingError),
            (NotSupportedError, sqlite3.NotSupportedError),
            (DatabaseError, sqlite3.DatabaseError),
            (PersistenceError, sqlite3.Error),
        ]
        for es_err, psy_err in errors:
            with self.assertRaises(es_err):
                with self.t:
                    raise psy_err


class TestSqliteDatastore(TestCase):
    def setUp(self) -> None:
        self.datastore = SQLiteDatastore(":memory:")

    def test_connect_failure_raises_interface_error(self):
        datastore = SQLiteDatastore(None)
        with self.assertRaises(InterfaceError):
            datastore.transaction()

    def test_transaction(self):
        transaction = self.datastore.transaction()
        with transaction as cursor:
            cursor.execute("SELECT 1")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]), 1)
            self.assertEqual(rows[0][0], 1)

    def test_sets_wal_journal_mode_if_not_memory(self):
        # Check datastore for in-memory database.
        with self.datastore.transaction():
            pass

        self.assertFalse(self.datastore.is_journal_mode_wal)
        self.assertFalse(self.datastore.journal_mode_was_changed_to_wal)

        # Create datastore for non-existing file database.
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        datastore = SQLiteDatastore(self.db_uri)

        with datastore.transaction():
            pass

        self.assertTrue(datastore.is_journal_mode_wal)
        self.assertTrue(datastore.journal_mode_was_changed_to_wal)

        datastore.close_all_connections()
        del datastore

        # Recreate datastore for existing database.
        datastore = SQLiteDatastore(self.db_uri)
        with datastore.transaction():
            pass
        self.assertTrue(datastore.is_journal_mode_wal)
        self.assertFalse(datastore.journal_mode_was_changed_to_wal)


class TestSQLiteAggregateRecorder(AggregateRecorderTestCase):
    def create_recorder(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        return recorder


class TestSQLiteAggregateRecorderErrors(TestCase):
    def test_raises_operational_error_when_creating_table_fails(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        # Broken create table statements.
        recorder.create_table_statements = ["BLAH"]
        with self.assertRaises(OperationalError):
            recorder.create_table()

    def test_raises_operational_error_when_inserting_fails(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        # Don't create table.
        with self.assertRaises(OperationalError):
            recorder.insert_events([])

    def test_raises_operational_error_when_selecting_fails(self):
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        # Don't create table.
        with self.assertRaises(OperationalError):
            recorder.select_events(uuid4())


class TestSQLiteApplicationRecorder(ApplicationRecorderTestCase):
    def create_recorder(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(self.db_uri))
        recorder.create_table()
        return recorder

    def test_insert_select(self):
        self.db_uri = ":memory:"
        super().test_insert_select()

    def test_concurrent_no_conflicts(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_concurrent_no_conflicts()

    def test_concurrent_no_conflicts_in_memory_db(self):
        self.db_uri = "file::memory:?cache=shared"
        super().test_concurrent_no_conflicts()

    def test_concurrent_throughput(self):
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_concurrent_throughput()

    def test_concurrent_throughput_in_memory_db(self):
        self.db_uri = "file::memory:?cache=shared"
        super().test_concurrent_throughput()


class TestSQLiteApplicationRecorderErrors(TestCase):
    def test_insert_raises_operational_error_if_table_not_created(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            # Haven't created table.
            recorder.insert_events([])

    def test_select_raises_operational_error_if_table_not_created(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.select_events(uuid4())

        with self.assertRaises(OperationalError):
            recorder.select_notifications(start=1, limit=1)

        with self.assertRaises(OperationalError):
            recorder.max_notification_id()


class TestSQLiteProcessRecorder(ProcessRecorderTestCase):
    def create_recorder(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        return recorder


class TestSQLiteProcessRecorderErrors(TestCase):
    def test_insert_raises_operational_error_if_table_not_created(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.insert_events([])

    def test_select_raises_operational_error_if_table_not_created(self):
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
        if Factory.SQLITE_LOCK_TIMEOUT in os.environ:
            del os.environ[Factory.SQLITE_LOCK_TIMEOUT]

    def test_construct_raises_environment_error_when_dbname_missing(self):
        del os.environ[Factory.SQLITE_DBNAME]
        with self.assertRaises(EnvironmentError) as cm:
            InfrastructureFactory.construct("TestCase")
        self.assertEqual(
            cm.exception.args[0],
            "SQLite database name not found in environment with key 'SQLITE_DBNAME'",
        )

    def test_environment_error_raised_when_lock_timeout_not_an_int(self):
        os.environ[Factory.SQLITE_LOCK_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            Factory("TestCase", os.environ)
        self.assertEqual(
            cm.exception.args[0],
            "SQLite environment value for key 'SQLITE_LOCK_TIMEOUT' "
            "is invalid. If set, an int or empty string is expected: 'abc'",
        )

    def test_lock_timeout_value(self):
        factory = Factory("TestCase", os.environ)
        self.assertEqual(factory.datastore.lock_timeout, None)

        os.environ[Factory.SQLITE_LOCK_TIMEOUT] = ""
        factory = Factory("TestCase", os.environ)
        self.assertEqual(factory.datastore.lock_timeout, None)

        os.environ[Factory.SQLITE_LOCK_TIMEOUT] = "10"
        factory = Factory("TestCase", os.environ)
        self.assertEqual(factory.datastore.lock_timeout, 10)


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecorderTestCase
del InfrastructureFactoryTestCase
