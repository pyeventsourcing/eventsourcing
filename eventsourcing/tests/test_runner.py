import os
from time import sleep
from typing import Type
from unittest.case import TestCase

from eventsourcing.postgres import (
    PostgresDatastore,
)
from eventsourcing.system import (
    AbstractRunner,
    MultiThreadedRunner,
    SingleThreadedRunner,
    System,
)
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.tests.test_application import BankAccounts
from eventsourcing.tests.test_postgres import drop_postgres_table
from eventsourcing.tests.test_processapplication import EmailNotifications


class TestSingleThreadedRunner(TestCase):
    runner_class: Type[AbstractRunner] = SingleThreadedRunner

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
        self.assertEqual(len(section.items), 0, section.items)

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


class TestMultiThreadedRunnerWithSQLite(TestMultiThreadedRunner):
    def setUp(self):
        os.environ["INFRASTRUCTURE_FACTORY"] = 'eventsourcing.sqlite:Factory'
        uris = tmpfile_uris()
        os.environ["DO_CREATE_TABLE"] = "y"
        os.environ["BANKACCOUNTS_SQLITE_DBNAME"] = next(uris)
        os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"] = next(uris)

    def tearDown(self):
        del os.environ["DO_CREATE_TABLE"]
        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["BANKACCOUNTS_SQLITE_DBNAME"]
        del os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"]


class TestMultiThreadedRunnerWithPostgres(TestMultiThreadedRunner):
    def setUp(self):
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"

        db = PostgresDatastore(
            os.getenv("POSTGRES_DBNAME"),
            os.getenv("POSTGRES_HOST"),
            os.getenv("POSTGRES_USER"),
            os.getenv("POSTGRES_PASSWORD"),
        )
        drop_postgres_table(db, "bankaccounts_events")
        drop_postgres_table(db, "emailnotifications_events")
        drop_postgres_table(db, "emailnotifications_tracking")

        os.environ["INFRASTRUCTURE_FACTORY"] = 'eventsourcing.postgres:Factory'
        os.environ["DO_CREATE_TABLE"] = "y"

    def tearDown(self):
        del os.environ["DO_CREATE_TABLE"]
        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
