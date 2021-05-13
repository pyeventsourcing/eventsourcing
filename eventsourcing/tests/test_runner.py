import os
from time import sleep
from typing import Type
from unittest.case import TestCase

from eventsourcing.postgres import PostgresDatastore
from eventsourcing.system import (
    MultiThreadedRunner,
    Runner,
    RunnerAlreadyStarted,
    SingleThreadedRunner,
    System,
)
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.tests.test_application import BankAccounts
from eventsourcing.tests.test_postgres import drop_postgres_table
from eventsourcing.tests.test_processapplication import EmailNotifications


class RunnerTestCase(TestCase):
    runner_class: Type[Runner] = Runner

    def test_runs_ok(self):
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

        with self.assertRaises(RunnerAlreadyStarted):
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


class TestSingleThreadedRunner(RunnerTestCase):
    runner_class: Type[Runner] = SingleThreadedRunner

    def test_prompts_received_doesnt_accumulate_names(self):
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

        with self.assertRaises(RunnerAlreadyStarted):
            runner.start()

        # Check prompts_received list doesn't accumulate.
        runner.is_prompting = True
        self.assertEqual(runner.prompts_received, [])
        runner.receive_prompt("BankAccounts")
        self.assertEqual(runner.prompts_received, ["BankAccounts"])
        runner.receive_prompt("BankAccounts")
        self.assertEqual(runner.prompts_received, ["BankAccounts"])
        runner.is_prompting = False


class TestMultiThreadedRunner(RunnerTestCase):
    runner_class = MultiThreadedRunner

    def wait_for_runner(self):
        sleep(0.1)

    class BrokenInitialisation(EmailNotifications):
        def __init__(self, *args, **kwargs):
            raise Exception("Testing exception is raised: broken initialisation")

    class BrokenProcessing(EmailNotifications):
        def pull_and_process(self, name: str) -> None:
            raise Exception("Testing exception is raised: broken processing")

    def test_stops_if_app_initialisation_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenInitialisation,
                ],
            ]
        )

        runner = self.runner_class(system)
        with self.assertRaises(Exception) as cm:
            runner.start()
        self.assertEqual(
            cm.exception.args[0], "Thread for 'BrokenInitialisation' failed to start"
        )
        self.assertTrue(runner.has_stopped)

    def test_stops_if_app_processing_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )

        runner = self.runner_class(system)
        runner.start()

        accounts = runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        self.wait_for_runner()

        self.assertTrue(runner.has_stopped)

    def test_prompts_received_doesnt_accumulate_names(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )

        runner = self.runner_class(system)
        runner.start()
        runner.stop()

        for thread in runner.threads.values():
            # Check the prompted names don't accumulate.
            self.assertEqual(thread.prompted_names, [])
            thread.receive_prompt("LeaderName")
            self.assertEqual(thread.prompted_names, ["LeaderName"])
            thread.receive_prompt("LeaderName")
            self.assertEqual(thread.prompted_names, ["LeaderName"])


class TestMultiThreadedRunnerWithSQLite(TestMultiThreadedRunner):
    def setUp(self):
        os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.sqlite:Factory"
        uris = tmpfile_uris()
        os.environ["BANKACCOUNTS_SQLITE_DBNAME"] = next(uris)
        os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPROCESSING_SQLITE_DBNAME"] = next(uris)

    def tearDown(self):
        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["BANKACCOUNTS_SQLITE_DBNAME"]
        del os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"]
        del os.environ["BROKENPROCESSING_SQLITE_DBNAME"]


class TestMultiThreadedRunnerWithPostgres(TestMultiThreadedRunner):
    def setUp(self):
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
        drop_postgres_table(db, "emailnotifications_events")
        drop_postgres_table(db, "emailnotifications_tracking")
        drop_postgres_table(db, "brokenprocessing_events")
        drop_postgres_table(db, "brokenprocessing_tracking")

        os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing.postgres:Factory"

    def tearDown(self):
        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]

    def test2_prompts_received_doesnt_accumulate_names(self):
        pass

    def test_prompts_received_doesnt_accumulate_names(self):

        super().test_prompts_received_doesnt_accumulate_names()


del RunnerTestCase
