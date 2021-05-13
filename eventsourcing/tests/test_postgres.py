import os
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
from eventsourcing.tests.processrecorder_testcase import ProcessRecordsTestCase
from eventsourcing.utils import get_topic


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

    def test_raises_operational_error_when_selecting_fails(self):
        # Construct the recorder.
        recorder = PostgresApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )

        with self.assertRaises(OperationalError):
            recorder.select_notifications(start=1, limit=1)

        with self.assertRaises(OperationalError):
            recorder.max_notification_id()


class TestPostgresProcessRecorder(ProcessRecordsTestCase):
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


class TestFactory(InfrastructureFactoryTestCase):
    def setUp(self) -> None:
        os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"
        super().setUp()

    def tearDown(self) -> None:
        if "POSTGRES_DBNAME" in os.environ:
            del os.environ["POSTGRES_DBNAME"]
        if "POSTGRES_HOST" in os.environ:
            del os.environ["POSTGRES_HOST"]
        if "POSTGRES_PORT" in os.environ:
            del os.environ["POSTGRES_PORT"]
        if "POSTGRES_USER" in os.environ:
            del os.environ["POSTGRES_USER"]
        if "POSTGRES_PASSWORD" in os.environ:
            del os.environ["POSTGRES_PASSWORD"]
        super().tearDown()

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
del ProcessRecordsTestCase
del InfrastructureFactoryTestCase


def drop_postgres_table(datastore: PostgresDatastore, table_name):
    try:
        with datastore.transaction() as c:
            statement = f"DROP TABLE {table_name};"
            print("Executing statement:", statement)
            c.execute(statement)
            print("Executed statement:", statement)
    except psycopg2.errors.lookup(UNDEFINED_TABLE):
        print("Failed to execute statement:", statement)
        pass  # print(f"Table does not exist: {table_name}")
    except Exception:
        print("Strange error:", statement)
