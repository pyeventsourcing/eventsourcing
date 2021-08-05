import os

from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.test_application_with_popo import (
    TIMEIT_FACTOR,
    TestApplicationWithPOPO,
)
from eventsourcing.tests.test_postgres import drop_postgres_table


class TestApplicationWithPostgres(TestApplicationWithPOPO):
    timeit_number = 5 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.postgres:Factory"

    def setUp(self) -> None:
        super().setUp()

        os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.postgres:Factory"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"

        db = PostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_PORT"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        drop_postgres_table(db, "bankaccounts_events")
        drop_postgres_table(db, "bankaccounts_snapshots")

    def tearDown(self) -> None:
        db = PostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_PORT"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        drop_postgres_table(db, "bankaccounts_events")
        drop_postgres_table(db, "bankaccounts_snapshots")

        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["CREATE_TABLE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        super().tearDown()


del TestApplicationWithPOPO
