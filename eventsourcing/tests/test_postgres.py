import os

import psycopg2
from psycopg2.errorcodes import UNDEFINED_TABLE

from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.postgres import (
    PostgresAggregateRecorder,
    PostgresApplicationRecorder,
    Factory,
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
            "eventsourcing",
            "eventsourcing",
        )
        drop_postgres_table(self.datastore, "stored_events")

    def create_recorder(self):
        recorder = PostgresAggregateRecorder(
            datastore=self.datastore,
            events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()

    def test_insert_and_select(self):
        super().test_insert_and_select()


class TestPostgresApplicationRecorder(ApplicationRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "eventsourcing",
            "eventsourcing",
        )
        drop_postgres_table(self.datastore, "stored_events")

    def create_recorder(self):
        recorder = PostgresApplicationRecorder(
            self.datastore,
            events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder


class TestPostgresProcessRecorder(ProcessRecordsTestCase):
    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "eventsourcing",
            "eventsourcing",
        )
        drop_postgres_table(self.datastore, "stored_events")
        drop_postgres_table(self.datastore, "notification_tracking")

    def create_recorder(self):
        recorder = PostgresProcessRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
            tracking_table_name="notification_tracking"
        )
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()


class TestFactory(InfrastructureFactoryTestCase):
    def setUp(self) -> None:
        os.environ[InfrastructureFactory.TOPIC] = get_topic(
            Factory
        )
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"
        super().setUp()

    def tearDown(self) -> None:
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        super().tearDown()


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecordsTestCase
del InfrastructureFactoryTestCase


def drop_postgres_table(datastore: PostgresDatastore, table_name):
    try:
        with datastore.transaction() as c:
            c.execute(f"DROP TABLE {table_name};")
    except psycopg2.errors.lookup(UNDEFINED_TABLE):
        print(f"Table does not exist: {table_name}")
