import os

from eventsourcing.async_postgres import AsyncPostgresDatastore
from eventsourcing.tests.test_application_with_popo import TIMEIT_FACTOR
from eventsourcing.tests.test_async_application_with_popo import (
    TestAsyncApplicationWithPOPO,
)
from eventsourcing.tests.test_async_postgres import drop_postgres_table
from eventsourcing.tests.test_postgres import pg_close_all_connections


class TestAsyncApplicationWithPostgres(TestAsyncApplicationWithPOPO):
    timeit_number = 5 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing.async_postgres:Factory"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()

        os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.async_postgres:Factory"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"

        db = await AsyncPostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_PORT"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        await drop_postgres_table(db, "bankaccounts_events")
        await drop_postgres_table(db, "bankaccounts_snapshots")

    async def asyncTearDown(self) -> None:
        db = await AsyncPostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_PORT"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        await drop_postgres_table(db, "bankaccounts_events")
        await drop_postgres_table(db, "bankaccounts_snapshots")
        pg_close_all_connections()

        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["CREATE_TABLE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        await super().asyncTearDown()


del TestAsyncApplicationWithPOPO
