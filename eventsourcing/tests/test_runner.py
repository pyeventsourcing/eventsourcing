import os
from time import sleep
from typing import Type
from unittest.case import TestCase

from eventsourcing.postgres import PostgresDatastore
from eventsourcing.system import (
    MultiThreadedRunner,
    ProcessingThreadError,
    PullingThreadError,
    Runner,
    RunnerAlreadyStarted,
    SingleThreadedRunner,
    System,
)
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.tests.test_application_with_popo import BankAccounts
from eventsourcing.tests.test_postgres import drop_postgres_table
from eventsourcing.tests.test_processapplication import EmailNotifications


class EmailNotifications2(EmailNotifications):
    pass


class RunnerTestCase(TestCase):
    runner_class: Type[Runner] = Runner

    def test_runs_ok(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    EmailNotifications,
                ],
                [
                    BankAccounts,
                    EmailNotifications2,
                ],
            ]
        )

        runner = self.runner_class(system)
        runner.start()

        with self.assertRaises(RunnerAlreadyStarted):
            runner.start()

        accounts = runner.get(BankAccounts)
        notifications1 = runner.get(EmailNotifications)
        notifications2 = runner.get(EmailNotifications2)

        section = notifications1.log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)

        section = notifications2.log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)

        for _ in range(10):
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

        self.wait_for_runner()

        section = notifications1.log["1,10"]
        self.assertEqual(len(section.items), 10)

        section = notifications2.log["1,10"]
        self.assertEqual(len(section.items), 10)

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
            raise Exception("Just testing error handling when initialisation is broken")

    class BrokenPulling(EmailNotifications):
        def pull_events(self, name, start):
            raise Exception("Just testing error handling when pulling is broken")

    class BrokenProcessing(EmailNotifications):
        def process_event(self, domain_event, process_event):
            raise Exception("Just testing error handling when processing is broken")

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
            cm.exception.args[0],
            "Just testing error handling when initialisation is broken",
        )
        self.assertTrue(runner.has_errored)

    def test_stop_raises_if_app_pulling_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenPulling,
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

        # Wait for runner to stop.
        runner.has_errored.wait()

        # Check stop() raises exception.
        with self.assertRaises(PullingThreadError) as cm:
            runner.stop()
        self.assertEqual(
            cm.exception.args[0], "Just testing error handling when pulling is broken"
        )

    def test_stop_raises_if_app_processing_is_broken(self):
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

        # Wait for runner to stop.
        runner.has_errored.wait()

        # Check stop() raises exception.
        with self.assertRaises(ProcessingThreadError) as cm:
            runner.stop()
        self.assertEqual(
            cm.exception.args[0],
            "Just testing error handling when processing is broken",
        )

    def test_watch_for_errors_raises_if_app_pulling_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenPulling,
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

        # Check watch_for_errors() raises exception.
        with self.assertRaises(PullingThreadError) as cm:
            runner.watch_for_errors()
        self.assertEqual(
            cm.exception.args[0], "Just testing error handling when pulling is broken"
        )

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

        # Check watch_for_errors() raises exception.
        with self.assertRaises(ProcessingThreadError) as cm:
            runner.watch_for_errors()
        self.assertEqual(
            cm.exception.args[0],
            "Just testing error handling when processing is broken",
        )


class TestMultiThreadedRunnerWithSQLiteFileBased(TestMultiThreadedRunner):
    def setUp(self):
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        uris = tmpfile_uris()
        os.environ["BANKACCOUNTS_SQLITE_DBNAME"] = next(uris)
        os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"] = next(uris)
        os.environ["EMAILNOTIFICATIONS2_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPROCESSING_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPULLING_SQLITE_DBNAME"] = next(uris)

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["BANKACCOUNTS_SQLITE_DBNAME"]
        del os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"]
        del os.environ["EMAILNOTIFICATIONS2_SQLITE_DBNAME"]
        del os.environ["BROKENPROCESSING_SQLITE_DBNAME"]
        del os.environ["BROKENPULLING_SQLITE_DBNAME"]

    def test_runs_ok(self):
        super().test_runs_ok()


class TestMultiThreadedRunnerWithSQLiteInMemory(TestMultiThreadedRunner):
    def setUp(self):
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ[
            "BANKACCOUNTS_SQLITE_DBNAME"
        ] = "file:bankaccounts?mode=memory&cache=shared"
        os.environ[
            "EMAILNOTIFICATIONS_SQLITE_DBNAME"
        ] = "file:emailnotifications1?mode=memory&cache=shared"
        os.environ[
            "EMAILNOTIFICATIONS2_SQLITE_DBNAME"
        ] = "file:emailnotifications2?mode=memory&cache=shared"
        os.environ[
            "BROKENPROCESSING_SQLITE_DBNAME"
        ] = "file:brokenprocessing?mode=memory&cache=shared"
        os.environ[
            "BROKENPULLING_SQLITE_DBNAME"
        ] = "file:brokenprocessing?mode=memory&cache=shared"

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["BANKACCOUNTS_SQLITE_DBNAME"]
        del os.environ["EMAILNOTIFICATIONS_SQLITE_DBNAME"]
        del os.environ["EMAILNOTIFICATIONS2_SQLITE_DBNAME"]
        del os.environ["BROKENPROCESSING_SQLITE_DBNAME"]
        del os.environ["BROKENPULLING_SQLITE_DBNAME"]

    def test_runs_ok(self):
        super().test_runs_ok()


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
        drop_postgres_table(db, "emailnotifications2_events")
        drop_postgres_table(db, "emailnotifications2_tracking")
        drop_postgres_table(db, "brokenprocessing_events")
        drop_postgres_table(db, "brokenprocessing_tracking")

        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]

    def wait_for_runner(self):
        sleep(0.5)


del RunnerTestCase
