from __future__ import annotations

import sqlite3
from sqlite3 import Connection
from typing import Any, Literal
from unittest import TestCase
from unittest.mock import Mock
from uuid import UUID, uuid4

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    ConnectionPool,
    DatabaseError,
    DataError,
    InfrastructureFactory,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    PersistenceError,
    ProcessRecorder,
    ProgrammingError,
    StoredEvent,
    Tracking,
    TrackingRecorder,
)
from eventsourcing.sqlite import (
    SQLiteAggregateRecorder,
    SQLiteApplicationRecorder,
    SQLiteConnectionPool,
    SQLiteDatastore,
    SQLiteFactory,
    SQLiteProcessRecorder,
    SQLiteTrackingRecorder,
    SQLiteTransaction,
)
from eventsourcing.tests.persistence import (
    AggregateRecorderTestCase,
    ApplicationRecorderTestCase,
    InfrastructureFactoryTestCase,
    ProcessRecorderTestCase,
    TrackingRecorderTestCase,
    tmpfile_uris,
)
from eventsourcing.utils import Environment
from tests.persistence_tests.test_connection_pool import TestConnectionPool


class TestTransaction(TestCase):
    def setUp(self) -> None:
        self.mock = Mock(Connection)
        self.t = SQLiteTransaction(self.mock, commit=True)

    def test_calls_commit_if_error_not_raised_during_transaction(self) -> None:
        with self.t:
            pass
        self.mock.commit.assert_called()
        self.mock.rollback.assert_not_called()

    def test_calls_rollback_if_error_is_raised_during_transaction(self) -> None:
        with self.assertRaises(TypeError), self.t:
            raise TypeError
        self.mock.commit.assert_not_called()
        self.mock.rollback.assert_called()

    def test_converts_errors_raised_in_transactions(self) -> None:
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
            with self.assertRaises(es_err), self.t:
                raise psy_err


class SQLiteConnectionPoolTestCase(TestConnectionPool):
    db_name: str

    def create_pool(
        self,
        *,
        pool_size: int = 1,
        max_overflow: int = 0,
        pool_timeout: float = 5.0,
        max_age: float | None = None,
        pre_ping: bool = False,
        mutually_exclusive_read_write: bool = True,
    ) -> ConnectionPool[Any]:
        return SQLiteConnectionPool(
            db_name=self.db_name,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            max_age=max_age,
            pre_ping=pre_ping,
        )

    def test_close_on_server_after_returning_with_pre_ping(self) -> None:
        pass

    def test_close_on_server_after_returning_without_pre_ping(self) -> None:
        pass


class TestSQLiteConnectionPoolWithInMemoryDB(SQLiteConnectionPoolTestCase):
    allowed_connecting_time = 0.01

    def setUp(self) -> None:
        self.db_name = ":memory:"

    def test_reader_writer(self) -> None:
        super()._test_reader_writer_with_mutually_exclusive_read_write()


class TestSQLiteConnectionPoolWithFileDB(SQLiteConnectionPoolTestCase):
    allowed_connecting_time = 0.01

    def setUp(self) -> None:
        self.tmp_urls = tmpfile_uris()
        self.db_name = next(self.tmp_urls)

    def test_reader_writer(self) -> None:
        super()._test_reader_writer_without_mutually_exclusive_read_write()


class TestSqliteDatastore(TestCase):
    def setUp(self) -> None:
        self.datastore = SQLiteDatastore(":memory:")

    def test_connect_failure_raises_interface_error(self) -> None:
        datastore = SQLiteDatastore(None)  # type: ignore[arg-type]
        with self.assertRaises(InterfaceError), datastore.transaction(commit=False):
            pass

    def test_transaction(self) -> None:
        transaction = self.datastore.transaction(commit=False)
        with transaction as cursor:
            cursor.execute("SELECT 1")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]), 1)
            self.assertEqual(rows[0][0], 1)

    def test_sets_wal_journal_mode_if_not_memory(self) -> None:
        # Check datastore for in-memory database.
        with self.datastore.transaction(commit=False):
            pass

        self.assertFalse(self.datastore.pool.is_journal_mode_wal)
        self.assertFalse(self.datastore.pool.journal_mode_was_changed_to_wal)

        # Create datastore for non-existing file database.
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        datastore = SQLiteDatastore(self.db_uri)

        with datastore.transaction(commit=False):
            pass

        self.assertTrue(datastore.pool.is_journal_mode_wal)
        self.assertTrue(datastore.pool.journal_mode_was_changed_to_wal)

        datastore.close()
        del datastore

        # Recreate datastore for existing database.
        datastore = SQLiteDatastore(self.db_uri)
        with datastore.transaction(commit=False):
            pass
        self.assertTrue(datastore.pool.is_journal_mode_wal)
        self.assertFalse(datastore.pool.journal_mode_was_changed_to_wal)


class TestSQLiteAggregateRecorder(AggregateRecorderTestCase):
    db_name = ":memory:"
    originator_id_type: Literal["uuid", "text"] = "uuid"

    def create_recorder(self) -> AggregateRecorder:
        recorder = SQLiteAggregateRecorder(
            SQLiteDatastore(
                db_name=self.db_name,
                originator_id_type=self.originator_id_type,
            )
        )
        recorder.create_table()
        return recorder


class WithTextOriginatorID:
    originator_id_type: Literal["uuid", "text"] = "text"

    def new_originator_id(self) -> UUID | str:
        return "test-" + str(uuid4())


class TestSQLiteAggregateRecorderWithTextOriginatorID(
    WithTextOriginatorID, TestSQLiteAggregateRecorder
):
    pass


class TestSQLiteAggregateRecorderErrors(TestCase):
    def test_raises_operational_error_when_creating_table_fails(self) -> None:
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        # Broken create table statements.
        recorder.create_table_statements = ["BLAH"]
        with self.assertRaises(OperationalError):
            recorder.create_table()

    def test_raises_operational_error_when_inserting_fails(self) -> None:
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        # Don't create table.
        with self.assertRaises(OperationalError):
            recorder.insert_events([])

    def test_raises_operational_error_when_selecting_fails(self) -> None:
        recorder = SQLiteAggregateRecorder(SQLiteDatastore(":memory:"))
        # Don't create table.
        with self.assertRaises(OperationalError):
            recorder.select_events(uuid4())


class TestSQLiteApplicationRecorder(
    ApplicationRecorderTestCase[SQLiteApplicationRecorder]
):
    db_uri = ":memory:"
    originator_id_type: Literal["uuid", "text"] = "uuid"

    def create_recorder(self) -> SQLiteApplicationRecorder:
        recorder = SQLiteApplicationRecorder(
            SQLiteDatastore(
                db_name=self.db_uri,
                pool_size=100,
                originator_id_type=self.originator_id_type,
            )
        )
        recorder.create_table()
        return recorder

    def test_insert_select(self) -> None:
        super().test_insert_select()

    def test_concurrent_no_conflicts(self, initial_position: int = 0) -> None:
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_concurrent_no_conflicts()

    def test_concurrent_no_conflicts_in_memory_db(self) -> None:
        self.db_uri = "file::memory:?cache=shared"
        super().test_concurrent_no_conflicts()

    def test_concurrent_throughput(self) -> None:
        self.uris = tmpfile_uris()
        self.db_uri = next(self.uris)
        super().test_concurrent_throughput()

    def test_concurrent_throughput_in_memory_db(self) -> None:
        self.db_uri = "file::memory:?cache=shared"
        super().test_concurrent_throughput()


class TestSQLiteApplicationRecorderWithTextOriginatorID(
    WithTextOriginatorID, TestSQLiteApplicationRecorder
):
    pass


class TestSQLiteApplicationRecorderErrors(TestCase):
    def test_insert_raises_operational_error_if_table_not_created(self) -> None:
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=1,
            topic="topic1",
            state=b"",
        )
        with self.assertRaises(OperationalError):
            # Haven't created table.
            recorder.insert_events([stored_event1])

    def test_select_raises_operational_error_if_table_not_created(self) -> None:
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.select_events(uuid4())

        with self.assertRaises(OperationalError):
            recorder.select_notifications(start=1, limit=1)

        with self.assertRaises(OperationalError):
            recorder.max_notification_id()

    def test_subscribe_raised_not_implemented_error(self) -> None:
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(NotImplementedError):
            recorder.subscribe(0)


class TestSQLiteTrackingRecorder(TrackingRecorderTestCase):
    def create_recorder(
        self,
        *,
        db_name: str = ":memory:",
        create_table: bool = True,
        single_row_tracking: bool = True,
    ) -> SQLiteTrackingRecorder:
        datastore = SQLiteDatastore(db_name, single_row_tracking=single_row_tracking)
        recorder = SQLiteTrackingRecorder(datastore)
        if create_table:
            recorder.create_table()
        return recorder

    def test_insert_tracking(self) -> None:
        super().test_insert_tracking()

    def test_initialise_single_row_tracking(self) -> None:
        recorder = self.create_recorder()
        self.assertFalse(recorder.tracking_table_exists)
        self.assertIsNone(recorder.tracking_migration_previous)
        self.assertEqual(1, recorder.tracking_migration_current)

    def test_raises_if_multi_row_tracking_with_single_row_table(self) -> None:
        uris = tmpfile_uris()
        db_uri = next(uris)

        recorder = self.create_recorder(db_name=db_uri)
        self.assertFalse(recorder.tracking_table_exists)
        self.assertIsNone(recorder.tracking_migration_previous)
        self.assertEqual(1, recorder.tracking_migration_current)

        with self.assertRaises(OperationalError):
            self.create_recorder(db_name=db_uri, single_row_tracking=False)

        recorder = self.create_recorder(
            db_name=db_uri, single_row_tracking=False, create_table=False
        )
        with self.assertRaises(OperationalError):
            recorder.insert_tracking(Tracking("upstream1", 10))

        with self.assertRaises(OperationalError):
            recorder.insert_tracking(Tracking("upstream1", 10))

    def test_migration_to_single_row_tracking(self) -> None:
        uris = tmpfile_uris()
        db_uri = next(uris)

        # Insert tracking single-row tracking, no table...
        recorder = self.create_recorder(db_name=db_uri, create_table=False)
        self.assertTrue(recorder.datastore.single_row_tracking)
        # Raises OperationalError because we haven't created the table.
        with self.assertRaises(OperationalError):
            recorder.insert_tracking(Tracking("upstream1", 1))
        self.assertFalse(recorder.tracking_table_exists)
        self.assertIsNone(recorder.tracking_migration_previous)

        # Insert tracking multi-row tracking, no table...
        recorder = self.create_recorder(
            db_name=db_uri, create_table=False, single_row_tracking=False
        )
        # Raises OperationalError because we haven't created the table.
        with self.assertRaises(OperationalError):
            recorder.insert_tracking(Tracking("upstream1", 1))
        self.assertFalse(recorder.tracking_table_exists)
        self.assertIsNone(recorder.tracking_migration_previous)

        # Create table for multi-row tracking.
        recorder.create_table()
        self.assertFalse(recorder.tracking_table_exists)
        self.assertIsNone(recorder.tracking_migration_previous)

        # Insert some tracking records.
        recorder.insert_tracking(Tracking("upstream1", 1))
        recorder.insert_tracking(Tracking("upstream1", 3))
        recorder.insert_tracking(Tracking("upstream2", 1))
        recorder.insert_tracking(Tracking("upstream2", 2))
        recorder.insert_tracking(Tracking("upstream2", 3))
        recorder.insert_tracking(Tracking("upstream2", 4))
        self.assertEqual(3, recorder.max_tracking_id("upstream1"))
        self.assertTrue(recorder.has_tracking_id("upstream1", 2))
        self.assertEqual(4, recorder.max_tracking_id("upstream2"))

        # Migrate table for multi-row tracking.
        recorder = self.create_recorder(db_name=db_uri, create_table=True)
        self.assertTrue(recorder.tracking_table_exists)
        self.assertIsNone(recorder.tracking_migration_previous)
        self.assertEqual(1, recorder.tracking_migration_current)

        # Check records have been migrated.
        self.assertEqual(3, recorder.max_tracking_id("upstream1"))
        self.assertTrue(recorder.has_tracking_id("upstream1", 2))
        self.assertEqual(4, recorder.max_tracking_id("upstream2"))

        # Recreate table and check records have been migrated.
        recorder = self.create_recorder(db_name=db_uri, create_table=True)
        self.assertTrue(recorder.tracking_table_exists)
        self.assertEqual(1, recorder.tracking_migration_previous)
        self.assertEqual(1, recorder.tracking_migration_current)


class TestSQLiteProcessRecorder(ProcessRecorderTestCase):
    originator_id_type: Literal["uuid", "text"] = "uuid"

    def create_recorder(self) -> ProcessRecorder:
        recorder = SQLiteProcessRecorder(
            SQLiteDatastore(
                db_name=":memory:",
                originator_id_type=self.originator_id_type,
            )
        )
        recorder.create_table()
        return recorder


class TestSQLiteProcessRecorderWithTextOriginatorID(
    WithTextOriginatorID, TestSQLiteProcessRecorder
):
    pass


class TestSQLiteProcessRecorderErrors(TestCase):
    def test_insert_raises_operational_error_if_table_not_created(self) -> None:
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        stored_event1 = StoredEvent(
            originator_id=uuid4(),
            originator_version=1,
            topic="topic1",
            state=b"",
        )
        with self.assertRaises(OperationalError):
            recorder.insert_events([stored_event1])

    def test_select_raises_operational_error_if_table_not_created(self) -> None:
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        with self.assertRaises(OperationalError):
            recorder.select_events(uuid4())

        with self.assertRaises(OperationalError):
            recorder.max_tracking_id("application name")


class TestSQLiteInfrastructureFactory(InfrastructureFactoryTestCase[SQLiteFactory]):
    def expected_factory_class(self) -> type[SQLiteFactory]:
        return SQLiteFactory

    def expected_aggregate_recorder_class(self) -> type[AggregateRecorder]:
        return SQLiteAggregateRecorder

    def expected_application_recorder_class(self) -> type[ApplicationRecorder]:
        return SQLiteApplicationRecorder

    def expected_tracking_recorder_class(self) -> type[TrackingRecorder]:
        return SQLiteTrackingRecorder

    class SQLiteTrackingRecorderSubclass(SQLiteTrackingRecorder):
        pass

    def tracking_recorder_subclass(self) -> type[TrackingRecorder]:
        return self.SQLiteTrackingRecorderSubclass

    def expected_process_recorder_class(self) -> type[ProcessRecorder]:
        return SQLiteProcessRecorder

    def setUp(self) -> None:
        self.env = Environment("TestCase")
        self.env[InfrastructureFactory.PERSISTENCE_MODULE] = SQLiteFactory.__module__
        self.env[SQLiteFactory.SQLITE_DBNAME] = ":memory:"
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        if SQLiteFactory.SQLITE_DBNAME in self.env:
            del self.env[SQLiteFactory.SQLITE_DBNAME]
        if SQLiteFactory.SQLITE_LOCK_TIMEOUT in self.env:
            del self.env[SQLiteFactory.SQLITE_LOCK_TIMEOUT]

    def test_construct_raises_environment_error_when_dbname_missing(self) -> None:
        del self.env[SQLiteFactory.SQLITE_DBNAME]
        with self.assertRaises(EnvironmentError) as cm:
            InfrastructureFactory.construct(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "SQLite database name not found in environment with keys: "
            "TESTCASE_SQLITE_DBNAME, SQLITE_DBNAME",
        )

    def test_environment_error_raised_when_lock_timeout_not_an_int(self) -> None:
        self.env[SQLiteFactory.SQLITE_LOCK_TIMEOUT] = "abc"
        with self.assertRaises(EnvironmentError) as cm:
            SQLiteFactory(self.env)
        self.assertEqual(
            cm.exception.args[0],
            "SQLite environment value for key 'SQLITE_LOCK_TIMEOUT' "
            "is invalid. If set, an int or empty string is expected: 'abc'",
        )

    def test_lock_timeout_value(self) -> None:
        factory = SQLiteFactory(self.env)
        self.assertEqual(factory.datastore.pool.lock_timeout, None)

        self.env[SQLiteFactory.SQLITE_LOCK_TIMEOUT] = ""
        factory = SQLiteFactory(self.env)
        self.assertEqual(factory.datastore.pool.lock_timeout, None)

        self.env[SQLiteFactory.SQLITE_LOCK_TIMEOUT] = "10"
        factory = SQLiteFactory(self.env)
        self.assertEqual(factory.datastore.pool.lock_timeout, 10)

    def test_single_row_tracking(self) -> None:
        factory = SQLiteFactory(self.env)
        self.assertEqual(factory.datastore.single_row_tracking, True)

        self.env[SQLiteFactory.SQLITE_SINGLE_ROW_TRACKING] = "f"
        factory = SQLiteFactory(self.env)
        self.assertEqual(factory.datastore.single_row_tracking, False)

    def test_originator_id_type(self) -> None:
        factory = SQLiteFactory(self.env)
        self.assertEqual(factory.datastore.originator_id_type, "uuid")

        self.env[SQLiteFactory.ORIGINATOR_ID_TYPE] = "text"
        factory = SQLiteFactory(self.env)
        self.assertEqual(factory.datastore.originator_id_type, "text")

        self.env[SQLiteFactory.ORIGINATOR_ID_TYPE] = "int"
        with self.assertRaises(OSError) as cm:
            SQLiteFactory(self.env)

        self.assertIn("Invalid ORIGINATOR_ID_TYPE", str(cm.exception))


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del TrackingRecorderTestCase
del ProcessRecorderTestCase
del InfrastructureFactoryTestCase
del SQLiteConnectionPoolTestCase
