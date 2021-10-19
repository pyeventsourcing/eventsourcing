from uuid import uuid4

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    ProcessRecorder,
    StoredEvent,
)
from eventsourcing.postgres import (
    PostgresAggregateRecorder,
    PostgresApplicationRecorder,
    PostgresDatastore,
    PostgresProcessRecorder,
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
from eventsourcing.tests.infrastructure_testcases import (
    InfrastructureFactoryTestCase,
)
from eventsourcing.tests.test_postgres import (
    drop_postgres_table,
    pg_close_all_connections,
)


class TestPostgresAggregateRecorder(AsyncAggregateRecorderTestCase):
    async def asyncSetUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    async def asyncTearDown(self) -> None:
        self.drop_tables()
        pg_close_all_connections()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")
        drop_postgres_table(self.datastore, "notification_tracking")

    async def create_recorder(self) -> AggregateRecorder:
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
        )
        recorder.create_table()
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


class TestPostgresApplicationRecorder(AsyncApplicationRecorderTestCase):
    async def asyncSetUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    async def asyncTearDown(self) -> None:
        self.drop_tables()
        pg_close_all_connections()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")
        drop_postgres_table(self.datastore, "notification_tracking")

    async def create_recorder(self) -> ApplicationRecorder:
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
        )
        recorder.create_table()
        return recorder

    async def test_insert_select(self):
        await super().test_insert_select()

    def test_concurrent_no_conflicts(self):
        super().test_concurrent_no_conflicts()

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
class TestPostgresProcessRecorder(AsyncProcessRecorderTestCase):
    async def asyncSetUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",
        )
        self.drop_tables()

    async def asyncTearDown(self) -> None:
        self.drop_tables()
        pg_close_all_connections()

    def drop_tables(self):
        drop_postgres_table(self.datastore, "stored_events")
        drop_postgres_table(self.datastore, "notification_tracking")

    async def create_recorder(self) -> ProcessRecorder:
        recorder = PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
            tracking_table_name="notification_tracking",
        )
        recorder.create_table()
        return recorder

    async def test_insert_select(self):
        await super().test_insert_select()

    async def test_performance(self):
        await super().test_performance()


del AsyncAggregateRecorderTestCase
del AsyncApplicationRecorderTestCase
del AsyncProcessRecorderTestCase
del InfrastructureFactoryTestCase
