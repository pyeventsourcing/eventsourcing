import os
from time import sleep
from typing import Type
from unittest.case import TestCase

from eventsourcing.domain import AggregateEvent
from eventsourcing.persistence import ProgrammingError
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.system import (
    AlwaysPull,
    ConvertingThread,
    EventProcessingError,
    MultiThreadedRunner,
    NeverPull,
    NotificationConvertingError,
    NotificationPullingError,
    ProcessingThread,
    PullGaps,
    PullingThread,
    Runner,
    RunnerAlreadyStarted,
    SingleThreadedRunner,
    System,
)
from eventsourcing.tests.ramdisk import tmpfile_uris
from eventsourcing.tests.test_aggregate import BankAccount
from eventsourcing.tests.test_application_with_popo import BankAccounts
from eventsourcing.tests.test_postgres import drop_postgres_table
from eventsourcing.tests.test_processapplication import EmailProcess
from eventsourcing.utils import get_topic


class EmailProcess2(EmailProcess):
    pass


class RunnerTestCase(TestCase):
    runner_class: Type[Runner] = SingleThreadedRunner

    def test_starts_with_single_app(self):
        system = System(pipes=[[BankAccounts]])
        runner = self.runner_class(system)
        runner.start()
        app = runner.get(BankAccounts)
        self.assertIsInstance(app, BankAccounts)

    def test_calling_start_twice_raises_error(self):
        system = System(pipes=[[BankAccounts]])
        runner = self.runner_class(system)
        runner.start()
        with self.assertRaises(RunnerAlreadyStarted):
            runner.start()

    def test_system_with_one_edge(self):
        system = System(pipes=[[BankAccounts, EmailProcess]])

        runner = self.runner_class(system)
        runner.start()

        accounts = runner.get(BankAccounts)
        email_process1 = runner.get(EmailProcess)

        section = email_process1.log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)

        for _ in range(10):
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

        self.wait_for_runner()

        section = email_process1.log["1,10"]
        self.assertEqual(len(section.items), 10)

        runner.stop()

    def test_system_with_two_edges(self):
        # Construct system and runner.
        system = System(
            pipes=[
                [
                    BankAccounts,
                    EmailProcess,
                ],
                [
                    BankAccounts,
                    EmailProcess2,
                ],
            ]
        )
        runner = self.runner_class(system)

        # Start the runner.
        runner.start()

        # Get apps.
        accounts = runner.get(BankAccounts)
        email_process1 = runner.get(EmailProcess)
        email_process2 = runner.get(EmailProcess2)

        # Check we processed nothing.
        section = email_process1.log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)
        section = email_process2.log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)

        # Create ten events.
        for _ in range(10):
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

        # Check we processed ten events.
        self.wait_for_runner()
        section = email_process1.log["1,10"]
        self.assertEqual(len(section.items), 10)
        section = email_process2.log["1,10"]
        self.assertEqual(len(section.items), 10)

        # Stop the runner.
        runner.stop()

    def test_follow_topics_always_pull_mode_catches_up(self):
        # Construct system and runner.
        system = System(pipes=[[BankAccounts, EmailProcess]])
        runner = self.runner_class(system)

        # Get apps.
        accounts = runner.get(BankAccounts)
        email_process1 = runner.get(EmailProcess)

        # Set follower topics.
        email_process1.follow_topics = [get_topic(BankAccount.Opened)]

        # Use the "always pull" mode.
        email_process1.pull_mode = AlwaysPull()

        # Create an event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start the runner.
        runner.start()

        # Check we processed nothing.
        self.wait_for_runner()
        self.assertEqual(len(email_process1.log["1,10"].items), 0)

        # Create another event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check we processed two events.
        self.wait_for_runner()
        self.assertEqual(len(email_process1.log["1,10"].items), 2)

        # Stop the runner.
        runner.stop()

    def test_follow_topics_pull_gaps_mode_catches_up(self):
        # Construct system and runner.
        system = System(pipes=[[BankAccounts, EmailProcess]])
        runner = self.runner_class(system)

        # Get apps.
        accounts = runner.get(BankAccounts)
        email_process1 = runner.get(EmailProcess)

        # Set follower topics.
        email_process1.follow_topics = [get_topic(BankAccount.Opened)]

        # Use the "pull gaps" mode.
        email_process1.pull_mode = PullGaps()

        # Create an event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start runner.
        runner.start()

        # Check we processed nothing.
        self.wait_for_runner()
        self.assertEqual(len(email_process1.log["1,10"].items), 0)

        # Create another event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check we processed two events.
        self.wait_for_runner()
        self.assertEqual(len(email_process1.log["1,10"].items), 2)

        # Stop the runner.
        runner.stop()

    def test_follow_topics_never_pull_mode_only_process_subsequent_notifications(self):
        # Construct system and runner.
        system = System(pipes=[[BankAccounts, EmailProcess]])
        runner = self.runner_class(system)

        # Get apps.
        accounts = runner.get(BankAccounts)
        email_process1 = runner.get(EmailProcess)

        # Use the "never pull" mode.
        email_process1.pull_mode = NeverPull()

        # Create an event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start the runner.
        runner.start()

        # Check we processed nothing.
        self.wait_for_runner()
        self.assertEqual(len(email_process1.log["1,10"].items), 0)

        # Fix follower topics.
        email_process1.follow_topics = [get_topic(BankAccount.Opened)]

        # Create another event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check we processed two events.
        self.wait_for_runner()
        self.assertEqual(len(email_process1.log["1,10"].items), 1)

        # Stop the runner.
        runner.stop()

    def wait_for_runner(self):
        pass


class TestSingleThreadedRunner(TestCase):
    runner_class: Type[Runner] = SingleThreadedRunner

    def test_prompts_received_dont_accumulate_names(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    EmailProcess,
                ],
            ]
        )

        runner = self.runner_class(system)
        runner.start()

        with self.assertRaises(RunnerAlreadyStarted):
            runner.start()

        # Check prompts_received list doesn't accumulate.
        runner.is_prompting = True
        self.assertEqual(runner.notifications_received, {})
        runner.receive_notifications(BankAccounts.name, [])
        self.assertEqual(runner.notifications_received, {BankAccounts.name: []})
        runner.receive_notifications(BankAccounts.name, [])
        self.assertEqual(runner.notifications_received, {BankAccounts.name: []})
        runner.is_prompting = False


class TestMultiThreadedRunner(RunnerTestCase):
    runner_class = MultiThreadedRunner

    def test_follow_topics_pull_gaps_mode_catches_up(self):
        super().test_follow_topics_pull_gaps_mode_catches_up()

    def wait_for_runner(self):
        sleep(0.1)

    class BrokenInitialisation(EmailProcess):
        def __init__(self, *args, **kwargs):
            raise ProgrammingError(
                "Just testing error handling when initialisation is broken"
            )

    class BrokenPulling(EmailProcess):
        def pull_notifications(self, leader_name, start):
            raise ProgrammingError("Just testing error handling when pulling is broken")

    class BrokenConverting(EmailProcess):
        def convert_notifications(self, mapper, name, notifications):
            raise ProgrammingError(
                "Just testing error handling when converting is broken"
            )

    class BrokenProcessing(EmailProcess):
        def process_event(self, domain_event, process_event):
            raise ProgrammingError(
                "Just testing error handling when processing is broken"
            )

    def test_stops_if_app_initialisation_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenInitialisation,
                ],
            ]
        )

        with self.assertRaises(Exception) as cm:
            self.runner_class(system)

        self.assertEqual(
            cm.exception.args[0],
            "Just testing error handling when initialisation is broken",
        )

    def test_stop_raises_if_notification_pulling_is_broken(self):
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
        self.assertTrue(runner.has_errored.wait(timeout=1))

        # Check stop() raises exception.
        with self.assertRaises(NotificationPullingError) as cm:
            runner.stop()
        self.assertIn(
            "Just testing error handling when pulling is broken",
            cm.exception.args[0],
        )

    def test_stop_raises_if_notification_converting_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenConverting,
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
        self.assertTrue(runner.has_errored.wait(timeout=1))

        # Check stop() raises exception.
        with self.assertRaises(NotificationConvertingError) as cm:
            runner.stop()
        self.assertIn(
            "Just testing error handling when converting is broken",
            cm.exception.args[0],
        )

    def test_stop_raises_if_event_processing_is_broken(self):
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
        self.assertTrue(runner.has_errored.wait(timeout=1))

        # Check stop() raises exception.
        with self.assertRaises(EventProcessingError) as cm:
            runner.stop()
        self.assertIn(
            "Just testing error handling when processing is broken",
            cm.exception.args[0],
        )

    def test_watch_for_errors_raises_if_runner_errors(self):
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
        with self.assertRaises(NotificationPullingError) as cm:
            runner.watch_for_errors(timeout=1)
        self.assertEqual(
            cm.exception.args[0], "Just testing error handling when pulling is broken"
        )

    def test_watch_for_errors_exits_without_raising_after_timeout(self):
        # Construct system and start runner
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

        # Watch for error with a timeout. Check returns False.
        self.assertFalse(runner.watch_for_errors(timeout=0.01))

        # Stop the runner.
        runner.stop()

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
        with self.assertRaises(EventProcessingError) as cm:
            runner.watch_for_errors(timeout=1)
        self.assertIn(
            "Just testing error handling when processing is broken",
            cm.exception.args[0],
        )


class TestMultiThreadedRunnerExtras(TestCase):
    def test_filters_notifications_by_follow_topics(self):
        system = System(pipes=[[BankAccounts, EmailProcess]])
        runner = MultiThreadedRunner(system)
        runner.start()

        accounts = runner.get(BankAccounts)
        email_process1 = runner.get(EmailProcess)

        email_process1.follow_topics = [get_topic(AggregateEvent)]
        email_process1.pull_mode = NeverPull()
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        sleep(0.1)

        for thread in runner.all_threads:
            if isinstance(thread, PullingThread):
                self.assertEqual(thread.last_id, 1)
            elif isinstance(thread, ProcessingThread):
                self.assertEqual(thread.last_id, 0)

        runner.stop()

    def test_queue_task_done_is_called(self):
        system = System(pipes=[[BankAccounts, EmailProcess]])
        runner = MultiThreadedRunner(system)
        runner.start()

        accounts = runner.get(BankAccounts)
        email_process1 = runner.get(EmailProcess)

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        sleep(0.1)
        self.assertEqual(len(email_process1.log["1,10"].items), 1)

        for thread in runner.all_threads:
            if isinstance(thread, PullingThread):
                self.assertEqual(thread.last_id, 1)
            elif isinstance(thread, ProcessingThread):
                self.assertEqual(thread.last_id, 1)
            elif isinstance(thread, ConvertingThread):
                self.assertEqual(thread.converting_queue.unfinished_tasks, 0)
                self.assertEqual(thread.processing_queue.unfinished_tasks, 0)

        runner.stop()


class TestMultiThreadedRunnerWithSQLiteFileBased(TestMultiThreadedRunner):
    def setUp(self):
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        uris = tmpfile_uris()
        os.environ[f"{BankAccounts.name.upper()}_SQLITE_DBNAME"] = next(uris)
        os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"] = next(uris)
        os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPROCESSING_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENCONVERTING_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPULLING_SQLITE_DBNAME"] = next(uris)

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ[f"{BankAccounts.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"]
        del os.environ["BROKENPROCESSING_SQLITE_DBNAME"]
        del os.environ["BROKENCONVERTING_SQLITE_DBNAME"]
        del os.environ["BROKENPULLING_SQLITE_DBNAME"]


class TestMultiThreadedRunnerWithSQLiteInMemory(TestMultiThreadedRunner):
    def setUp(self):
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ[
            f"{BankAccounts.name.upper()}_SQLITE_DBNAME"
        ] = f"file:{BankAccounts.name.lower()}?mode=memory&cache=shared"
        os.environ[
            f"{EmailProcess.name.upper()}_SQLITE_DBNAME"
        ] = f"file:{EmailProcess.name.lower()}?mode=memory&cache=shared"
        os.environ[
            f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"
        ] = f"file:{EmailProcess.name.lower()}2?mode=memory&cache=shared"
        os.environ[
            "BROKENPROCESSING_SQLITE_DBNAME"
        ] = "file:brokenprocessing?mode=memory&cache=shared"
        os.environ[
            "BROKENCONVERTING_SQLITE_DBNAME"
        ] = "file:brokenconverting?mode=memory&cache=shared"
        os.environ[
            "BROKENPULLING_SQLITE_DBNAME"
        ] = "file:brokenprocessing?mode=memory&cache=shared"

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ[f"{BankAccounts.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"]
        del os.environ["BROKENPROCESSING_SQLITE_DBNAME"]
        del os.environ["BROKENCONVERTING_SQLITE_DBNAME"]
        del os.environ["BROKENPULLING_SQLITE_DBNAME"]


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
        drop_postgres_table(db, f"{BankAccounts.name.lower()}_events")
        drop_postgres_table(db, f"{EmailProcess.name.lower()}_events")
        drop_postgres_table(db, f"{EmailProcess.name.lower()}_tracking")
        drop_postgres_table(db, f"{EmailProcess.name.lower()}2_events")
        drop_postgres_table(db, f"{EmailProcess.name.lower()}2_tracking")
        drop_postgres_table(db, "brokenprocessing_events")
        drop_postgres_table(db, "brokenconverting_events")
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
