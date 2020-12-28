import os
from time import sleep
from typing import Type
from unittest.case import TestCase

import psycopg2.errors
from psycopg2.errorcodes import UNDEFINED_TABLE

from eventsourcing.utils import get_topic
from eventsourcing.bankaccounts import (
    BankAccounts,
)
from eventsourcing.emailnotifications import (
    EmailNotifications,
)
from eventsourcing.multithreadedrunner import (
    MultiThreadedRunner,
)
from eventsourcing.postgresrecorders import (
    PostgresDatabase,
    PostgresInfrastructureFactory,
)
from eventsourcing.ramdisk import tmpfile_uris
from eventsourcing.singlethreadedrunner import (
    SingleThreadedRunner,
)
from eventsourcing.sqliterecorders import (
    SQLiteInfrastructureFactory,
)
from eventsourcing.system import System
from eventsourcing.systemrunner import AbstractRunner


class TestSingleThreadedRunner(TestCase):
    runner_class: Type[
        AbstractRunner
    ] = SingleThreadedRunner

    def setUp(self):
        os.environ["DB_URI"] = ":memory:"

    def tearDown(self):
        del os.environ["DB_URI"]

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
        os.environ["BANKACCOUNTS_DB_URI"] = next(uris)
        os.environ["EMAILNOTIFICATIONS_DB_URI"] = next(
            uris
        )

    def tearDown(self):
        del os.environ["DO_CREATE_TABLE"]
        del os.environ["INFRASTRUCTURE_FACTORY_TOPIC"]
        del os.environ["BANKACCOUNTS_DB_URI"]
        del os.environ["EMAILNOTIFICATIONS_DB_URI"]


class TestMultiThreadedRunnerWithPostgres(
    TestMultiThreadedRunner
):
    def setUp(self):
        def drop_table(table_name):
            db = PostgresDatabase()
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
