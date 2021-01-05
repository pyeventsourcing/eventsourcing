import os

import psycopg2.errors
from psycopg2.errorcodes import UNDEFINED_TABLE

from eventsourcing.tests.infrastructure_testcases import InfrastructureFactoryTestCase
from eventsourcing.infrastructurefactory import InfrastructureFactory
from eventsourcing.postgresrecorders import PostgresAggregateRecorder, \
    PostgresApplicationRecorder, PostgresInfrastructureFactory, PostgresProcessRecorder
from eventsourcing.tests.aggregaterecorder_testcase import AggregateRecorderTestCase
from eventsourcing.tests.applicationrecorder_testcase import ApplicationRecorderTestCase
from eventsourcing.tests.processrecorder_testcase import ProcessRecordsTestCase
from eventsourcing.utils import get_topic


class TestPostgresAggregateRecorder(AggregateRecorderTestCase):
    def setUp(self) -> None:
        recorder = PostgresAggregateRecorder(
            "",
            os.getenv("POSTGRES_DBNAME", "eventsourcing"),
            os.getenv("POSTGRES_HOST", "127.0.0.1"),
            os.getenv("POSTGRES_USER", "eventsourcing"),
            os.getenv("POSTGRES_PASSWORD", "eventsourcing"),
        )
        try:
            with recorder.db.transaction() as c:
                c.execute("DROP TABLE stored_events;")
        except psycopg2.errors.lookup(UNDEFINED_TABLE):
            pass

    def create_recorder(self):
        recorder = PostgresAggregateRecorder(
            "",
            os.getenv("POSTGRES_DBNAME", "eventsourcing"),
            os.getenv("POSTGRES_HOST", "127.0.0.1"),
            os.getenv("POSTGRES_USER", "eventsourcing"),
            os.getenv("POSTGRES_PASSWORD", "eventsourcing"),
        )
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()

    def test_insert_and_select(self):
        super().test_insert_and_select()


class TestPostgresApplicationRecorder(
    ApplicationRecorderTestCase
):
    def setUp(self) -> None:
        recorder = PostgresApplicationRecorder(
            "",
            os.getenv("POSTGRES_DBNAME", "eventsourcing"),
            os.getenv("POSTGRES_HOST", "127.0.0.1"),
            os.getenv("POSTGRES_USER", "eventsourcing"),
            os.getenv("POSTGRES_PASSWORD", "eventsourcing"),
        )
        try:
            with recorder.db.transaction() as c:
                c.execute("DROP TABLE events;")
        except psycopg2.errors.lookup(UNDEFINED_TABLE):
            pass

    def create_recorder(self):
        recorder = PostgresApplicationRecorder(
            "",
            os.getenv("POSTGRES_DBNAME", "eventsourcing"),
            os.getenv("POSTGRES_HOST", "127.0.0.1"),
            os.getenv("POSTGRES_USER", "eventsourcing"),
            os.getenv("POSTGRES_PASSWORD", "eventsourcing"),
        )
        recorder.create_table()
        return recorder


class TestPostgresProcessRecorder(ProcessRecordsTestCase):
    def setUp(self) -> None:
        recorder = PostgresProcessRecorder(
            "",
            os.getenv("POSTGRES_DBNAME", "eventsourcing"),
            os.getenv("POSTGRES_HOST", "127.0.0.1"),
            os.getenv("POSTGRES_USER", "eventsourcing"),
            os.getenv("POSTGRES_PASSWORD", "eventsourcing"),
        )
        try:
            with recorder.db.transaction() as c:
                c.execute("DROP TABLE stored_events;")
        except psycopg2.errors.lookup(UNDEFINED_TABLE):
            pass
        try:
            with recorder.db.transaction() as c:
                c.execute("DROP TABLE tracking;")
        except psycopg2.errors.lookup(UNDEFINED_TABLE):
            pass

    def create_recorder(self):
        recorder = PostgresProcessRecorder(
            "",
            os.getenv("POSTGRES_DBNAME", "eventsourcing"),
            os.getenv("POSTGRES_HOST", "127.0.0.1"),
            os.getenv("POSTGRES_USER", "eventsourcing"),
            os.getenv("POSTGRES_PASSWORD", "eventsourcing"),
        )
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()


class TestPostgresInfrastructureFactory(
    InfrastructureFactoryTestCase
):
    def setUp(self) -> None:
        os.environ[
            InfrastructureFactory.TOPIC
        ] = get_topic(PostgresInfrastructureFactory)

        if "POSTGRES_DBNAME" not in os.environ:
            os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        if "POSTGRES_HOST" not in os.environ:
            os.environ["POSTGRES_HOST"] = "127.0.0.1"
        if "POSTGRES_USER" not in os.environ:
            os.environ["POSTGRES_USER"] = "eventsourcing"
        if "POSTGRES_PASSWORD" not in os.environ:
            os.environ["POSTGRES_PASSWORD"] = "eventsourcing"

        super().setUp()


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecordsTestCase
del InfrastructureFactoryTestCase


