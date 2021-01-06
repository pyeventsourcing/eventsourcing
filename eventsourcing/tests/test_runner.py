import os
from time import sleep
from typing import Type
from unittest.case import TestCase

import psycopg2.errors
from psycopg2.errorcodes import UNDEFINED_TABLE

from eventsourcing.tests.test_application import BankAccounts
from eventsourcing.utils import get_topic
from eventsourcing.tests.test_processapplication import EmailNotifications
from eventsourcing.postgres import (
    PostgresDatabase,
    PostgresInfrastructureFactory,
)
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.sqliterecorders import (
    SQLiteInfrastructureFactory,
)
from eventsourcing.system import AbstractRunner, MultiThreadedRunner, \
    SingleThreadedRunner, System


class TestSingleThreadedRunner(TestCase):
    runner_class: Type[
        AbstractRunner
    ] = SingleThreadedRunner

    def test(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    EmailNotifications,
                ],
            ]
        )

        runner = self.runner_class(system)

        runner.start()
        accounts = runner.get(BankAccounts)
        notifications = runner.get(EmailNotifications)

        section = notifications.log["1,5"]
        self.assertEqual(
            len(section.items), 0, section.items
        )

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        self.wait_for_runner()

        section = notifications.log["1,5"]
        self.assertEqual(len(section.items), 1)

        runner.stop()

    def wait_for_runner(self):
        pass


class TestMultiThreadedRunner(TestSingleThreadedRunner):
    runner_class = MultiThreadedRunner

    def wait_for_runner(self):
        sleep(0.1)


class TestMultiThreadedRunnerWithSQLite(
    TestMultiThreadedRunner
):
    def setUp(self):
        topic = get_topic(SQLiteInfrastructureFactory)
        os.environ["INFRASTRUCTURE_FACTORY_TOPIC"] = topic
        uris = tmpfile_uris()
        os.environ["DO_CREATE_TABLE"] = "y"
        os.environ["BANKACCOUNTS_SQLITE_DBNAME"] = next(uris)
        os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"] = next(
            uris
        )

    def tearDown(self):
        del os.environ["DO_CREATE_TABLE"]
        del os.environ["INFRASTRUCTURE_FACTORY_TOPIC"]
        del os.environ["BANKACCOUNTS_SQLITE_DBNAME"]
        del os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"]


class TestMultiThreadedRunnerWithPostgres(
    TestMultiThreadedRunner
):
    def setUp(self):
        if "POSTGRES_DBNAME" not in os.environ:
            os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        if "POSTGRES_HOST" not in os.environ:
            os.environ["POSTGRES_HOST"] = "127.0.0.1"
        if "POSTGRES_USER" not in os.environ:
            os.environ["POSTGRES_USER"] = "eventsourcing"
        if "POSTGRES_PASSWORD" not in os.environ:
            os.environ["POSTGRES_PASSWORD"] = "eventsourcing"

        def drop_table(table_name):
            db = PostgresDatabase(
                os.getenv("POSTGRES_DBNAME"),
                os.getenv("POSTGRES_HOST"),
                os.getenv("POSTGRES_USER"),
                os.getenv("POSTGRES_PASSWORD"),
            )
            try:
                with db.transaction() as c:
                    c.execute(f"DROP TABLE {table_name};")
            except psycopg2.errors.lookup(UNDEFINED_TABLE):
                pass

        drop_table("bankaccountsevents")
        drop_table("emailnotificationsevents")
        drop_table("emailnotificationstracking")

        topic = get_topic(PostgresInfrastructureFactory)
        os.environ["INFRASTRUCTURE_FACTORY_TOPIC"] = topic
        os.environ["DO_CREATE_TABLE"] = "y"

    def tearDown(self):
        del os.environ["DO_CREATE_TABLE"]
        del os.environ["INFRASTRUCTURE_FACTORY_TOPIC"]
