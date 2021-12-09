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

        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"
        os.environ["POSTGRES_SCHEMA"] = "public"

        db = PostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_PORT"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        drop_postgres_table(db, "public.bankaccounts_events")
        drop_postgres_table(db, "public.bankaccounts_snapshots")
        db.close()

    def tearDown(self) -> None:
        db = PostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_PORT"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        drop_postgres_table(db, "public.bankaccounts_events")
        drop_postgres_table(db, "public.bankaccounts_snapshots")

        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["CREATE_TABLE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        del os.environ["POSTGRES_SCHEMA"]
        db.close()

        super().tearDown()


del TestApplicationWithPOPO
