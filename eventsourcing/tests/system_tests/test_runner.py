import os
import shlex
import subprocess
from queue import Queue
from threading import Event
from time import sleep
from typing import Generic, Iterable, List, Optional, Tuple, Type, TypeVar
from unittest.case import TestCase
from unittest.mock import MagicMock
from uuid import UUID

from eventsourcing.application import ProcessingEvent, RecordingEvent
from eventsourcing.domain import Aggregate, AggregateEvent, event
from eventsourcing.persistence import Notification, ProgrammingError
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.system import (
    ConvertingThread,
    EventProcessingError,
    MultiThreadedRunner,
    NewMultiThreadedRunner,
    NewSingleThreadedRunner,
    NotificationConvertingError,
    NotificationPullingError,
    ProcessApplication,
    ProcessingJob,
    PullingThread,
    Runner,
    RunnerAlreadyStarted,
    SingleThreadedRunner,
    System,
)
from eventsourcing.tests.application import BankAccounts
from eventsourcing.tests.application_tests.test_processapplication import (
    EmailProcess,
)
from eventsourcing.tests.persistence import tmpfile_uris
from eventsourcing.tests.postgres_utils import drop_postgres_table
from eventsourcing.utils import clear_topic_cache, get_topic


class EmailProcess2(EmailProcess):
    pass


TRunner = TypeVar("TRunner", bound=Runner)


class RunnerTestCase(TestCase, Generic[TRunner]):
    runner_class: Type[TRunner]
    runner: Optional[TRunner]

    def setUp(self) -> None:
        self.runner: Optional[TRunner] = None

    def tearDown(self) -> None:
        if self.runner:
            try:
                self.runner.stop()
            except Exception as e:
                raise Exception("Runner errored: " + str(e))

    def start_runner(self, system):
        self.runner = self.runner_class(system)
        self.runner.start()

    def test_runner_constructed_with_env_has_apps_with_env(self):
        system = System(pipes=[[BankAccounts, EmailProcess]])
        env = {"MY_ENV_VAR": "my_env_val"}
        self.runner = self.runner_class(system, env)
        self.runner.start()

        # Check leaders get the environment.
        app = self.runner.get(BankAccounts)
        self.assertEqual(app.env.get("MY_ENV_VAR"), "my_env_val")

        # Check followers get the environment.
        app = self.runner.get(EmailProcess)
        self.assertEqual(app.env.get("MY_ENV_VAR"), "my_env_val")

        # Stop the runner before we start another.
        self.runner.stop()

        # Check singles get the environment.
        system = System(pipes=[[BankAccounts]])
        env = {"MY_ENV_VAR": "my_env_val"}
        self.runner = self.runner_class(system, env)
        self.runner.start()
        app = self.runner.get(BankAccounts)
        self.assertEqual(app.env.get("MY_ENV_VAR"), "my_env_val")

    def test_starts_with_single_app(self):
        self.start_runner(System(pipes=[[BankAccounts]]))
        app = self.runner.get(BankAccounts)
        self.assertIsInstance(app, BankAccounts)

    def test_calling_start_twice_raises_error(self):
        self.start_runner(System(pipes=[[BankAccounts]]))
        with self.assertRaises(RunnerAlreadyStarted):
            self.runner.start()

    def test_system_with_one_edge(self):
        self.start_runner(System(pipes=[[BankAccounts, EmailProcess]]))
        accounts = self.runner.get(BankAccounts)
        email_process = self.runner.get(EmailProcess)

        section = email_process.notification_log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)

        for _ in range(10):
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

        self.wait_for_runner()

        section = email_process.notification_log["1,10"]
        self.assertEqual(len(section.items), 10)

    def test_system_with_two_edges(self):
        clear_topic_cache()

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
        self.start_runner(system)

        # Get apps.
        accounts = self.runner.get(BankAccounts)
        email_process1 = self.runner.get(EmailProcess)
        email_process2 = self.runner.get(EmailProcess2)

        # Check we processed nothing.
        section = email_process1.notification_log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)
        section = email_process2.notification_log["1,5"]
        self.assertEqual(len(section.items), 0, section.items)

        # Create ten events.
        for _ in range(10):
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

        # Check we processed ten events.
        self.wait_for_runner()
        section = email_process1.notification_log["1,10"]
        self.assertEqual(len(section.items), 10)
        section = email_process2.notification_log["1,10"]
        self.assertEqual(len(section.items), 10)

    def test_system_with_processing_loop(self):
        class Command(Aggregate):
            def __init__(self, text: str):
                self.text = text
                self.output: Optional[str] = None
                self.error: Optional[str] = None

            @event
            def done(self, output: str, error: str):
                self.output = output
                self.error = error

        class Result(Aggregate):
            def __init__(self, command_id: UUID, output: str, error: str):
                self.command_id = command_id
                self.output = output
                self.error = error

        class Commands(ProcessApplication):
            def create_command(self, text: str) -> UUID:
                command = Command(text=text)
                self.save(command)
                return command.id

            def policy(
                self,
                domain_event: AggregateEvent[Aggregate],
                processing_event: ProcessingEvent,
            ) -> None:
                if isinstance(domain_event, Result.Created):
                    command = self.repository.get(domain_event.command_id)
                    command.done(
                        output=domain_event.output,
                        error=domain_event.error,
                    )
                    processing_event.collect_events(command)

            def get_result(self, command_id: UUID) -> Tuple[str, str]:
                command = self.repository.get(command_id)
                return command.output, command.error

        class Results(ProcessApplication):
            def policy(
                self,
                domain_event: AggregateEvent[Aggregate],
                processing_event: ProcessingEvent,
            ) -> None:
                if isinstance(domain_event, Command.Created):
                    try:
                        output = subprocess.check_output(shlex.split(domain_event.text))
                        error = ""
                    except Exception as e:
                        error = str(e)
                        output = b""
                    result = Result(
                        command_id=domain_event.originator_id,
                        output=output.decode("utf8"),
                        error=error,
                    )
                    processing_event.collect_events(result)

        self.start_runner(System([[Commands, Results, Commands]]))

        commands = self.runner.get(Commands)
        command_id1 = commands.create_command("echo 'Hello World'")
        command_id2 = commands.create_command("notacommand")

        self.wait_for_runner()
        self.wait_for_runner()

        for _ in range(10):
            output, error = commands.get_result(command_id1)
            if output is None:
                sleep(0.1)
            else:
                break
        else:
            self.fail("No results from command")

        self.assertEqual(output, "Hello World\n")
        self.assertEqual(error, "")

        for _ in range(10):
            output, error = commands.get_result(command_id2)
            if output is None:
                sleep(0.1)
            else:
                break
        else:
            self.fail("No results from command")

        self.assertEqual(output, "")
        self.assertIn("No such file or directory: 'notacommand'", error)

    def test_catches_up_with_outstanding_notifications(self):
        # Construct system and runner.
        system = System(pipes=[[BankAccounts, EmailProcess]])
        self.runner = self.runner_class(system)

        # Get apps.
        accounts = self.runner.get(BankAccounts)
        email_process1 = self.runner.get(EmailProcess)

        # Create an event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check we processed nothing.
        self.assertEqual(email_process1.recorder.max_tracking_id("BankAccounts"), 0)

        # Start the runner.
        self.runner.start()

        # Create another event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check we processed two events.
        self.wait_for_runner()
        self.assertEqual(email_process1.recorder.max_tracking_id("BankAccounts"), 2)

    def test_filters_notifications_by_follow_topics(self):
        class MyEmailProcess(EmailProcess):
            follow_topics = [get_topic(AggregateEvent)]  # follow nothing

        system = System(pipes=[[BankAccounts, MyEmailProcess]])
        self.runner = self.runner_class(system)

        accounts = self.runner.get(BankAccounts)
        email_process = self.runner.get(MyEmailProcess)

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        self.runner.start()

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        self.wait_for_runner()

        self.assertEqual(len(email_process.notification_log["1,10"].items), 0)

    def wait_for_runner(self):
        pass


class SingleThreadedRunnerFollowersOrderingMixin:
    """Followers ordering tests for single-threaded runners."""

    def test_followers_are_prompted_in_declaration_order(self):
        """Validate the order in which followers are prompted by the runner.

        This test can, by nature, show some flakiness. That is, we can
        see false negatives at times when a random ordering would match
        the expected ordering. We mitigate this problem by increasing
        the number of followers to be ordered.
        """
        clear_topic_cache()
        app_calls = []

        class NameLogger(EmailProcess):
            def policy(self, domain_event, processing_event):
                app_calls.append(self.__class__.__name__)

        def make_name_logger(n: int) -> Type:
            return type(f"NameLogger{n}", (NameLogger,), {})

        # Construct system and runner.
        system = System(
            pipes=[
                [BankAccounts, make_name_logger(3)],
                [BankAccounts, make_name_logger(4)],
                [BankAccounts, make_name_logger(1)],
                [BankAccounts, make_name_logger(5)],
                [BankAccounts, make_name_logger(2)],
            ]
        )
        self.start_runner(system)

        # Create an event.
        self.runner.get(BankAccounts).open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        self.wait_for_runner()

        # Check the applications' policy were called in the right order.
        self.assertEqual(
            app_calls,
            ["NameLogger3", "NameLogger4", "NameLogger1", "NameLogger5", "NameLogger2"],
        )


class TestSingleThreadedRunner(
    RunnerTestCase[SingleThreadedRunner], SingleThreadedRunnerFollowersOrderingMixin
):
    runner_class = SingleThreadedRunner


class TestNewSingleThreadedRunner(
    RunnerTestCase[NewSingleThreadedRunner], SingleThreadedRunnerFollowersOrderingMixin
):
    runner_class = NewSingleThreadedRunner

    def test_ignores_recording_event_if_seen_subsequent(self):
        system = System(pipes=[[BankAccounts, EmailProcess]])
        self.start_runner(system)

        accounts = self.runner.get(BankAccounts)
        email_process = self.runner.get(EmailProcess)

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        self.wait_for_runner()

        self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

        # Reset this to break sequence.
        accounts.previous_max_notification_id -= 1

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        self.wait_for_runner()

        self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

    def test_received_notifications_accumulate(self):
        self.start_runner(
            System(
                [
                    [
                        BankAccounts,
                        EmailProcess,
                    ]
                ]
            )
        )

        accounts = self.runner.get(BankAccounts)
        # Need to get the lock, so that they aren't cleared.
        with self.runner._processing_lock:
            accounts.open_account("Alice", "alice@example.com")
            self.assertEqual(len(self.runner._recording_events_received), 1)
            accounts.open_account("Bob", "bob@example.com")
            self.assertEqual(len(self.runner._recording_events_received), 2)


class TestPullingThread(TestCase):
    def test_receive_recording_event_does_not_block(self):
        thread = PullingThread(
            converting_queue=Queue(),
            follower=MagicMock(),
            leader_name="BankAccounts",
            has_errored=Event(),
        )
        thread.recording_event_queue.maxsize = 1
        self.assertEqual(thread.recording_event_queue.qsize(), 0)
        thread.receive_recording_event(
            RecordingEvent(
                application_name="BankAccounts",
                recordings=[],
                previous_max_notification_id=None,
            )
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 1)
        self.assertFalse(thread.overflow_event.is_set())
        thread.receive_recording_event(
            RecordingEvent(
                application_name="BankAccounts",
                recordings=[],
                previous_max_notification_id=1,
            )
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 1)
        self.assertTrue(thread.overflow_event.is_set())

    def test_stops_because_stopping_event_is_set(self):
        thread = PullingThread(
            converting_queue=Queue(),
            follower=MagicMock(),
            leader_name="BankAccounts",
            has_errored=Event(),
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 0)
        thread.receive_recording_event(
            RecordingEvent(
                application_name="BankAccounts",
                recordings=[],
                previous_max_notification_id=None,
            )
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 1)
        thread.stop()  # Set 'is_stopping' event.
        self.assertEqual(thread.recording_event_queue.qsize(), 2)
        thread.start()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(thread.recording_event_queue.qsize(), 2)

    def test_stops_because_recording_event_queue_was_poisoned(self):
        thread = PullingThread(
            converting_queue=Queue(),
            follower=MagicMock(),
            leader_name="BankAccounts",
            has_errored=Event(),
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 0)
        thread.start()
        thread.stop()  # Poison queue.
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(thread.recording_event_queue.qsize(), 0)


class TestMultiThreadedRunner(RunnerTestCase[MultiThreadedRunner]):
    runner_class = MultiThreadedRunner

    def test_ignores_recording_event_if_seen_subsequent(self):
        # Skipping this because this runner doesn't take
        # notice of attribute previous_max_notification_id.
        pass

    def wait_for_runner(self):
        sleep(0.3)
        try:
            self.runner.reraise_thread_errors()
        except Exception as e:
            self.runner = None
            raise Exception("Runner errored: " + str(e)) from e

    class BrokenInitialisation(EmailProcess):
        def __init__(self, *args, **kwargs):
            raise ProgrammingError(
                "Just testing error handling when initialisation is broken"
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

    def test_stop_raises_if_event_processing_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )
        self.start_runner(system)

        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Wait for runner to stop.
        self.assertTrue(self.runner.has_errored.wait(timeout=1))

        # Check stop() raises exception.
        with self.assertRaises(EventProcessingError) as cm:
            self.runner.stop()
        self.assertIn(
            "Just testing error handling when processing is broken",
            cm.exception.args[0],
        )
        self.runner = None

    def test_watch_for_errors_raises_if_runner_errors(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )
        # Create runner.
        self.runner = self.runner_class(system)

        # Create some notifications.
        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start runner.
        self.runner.start()

        # Trigger pulling of notifications.
        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check watch_for_errors() raises exception.
        with self.assertRaises(EventProcessingError) as cm:
            self.runner.watch_for_errors(timeout=1)
        self.assertEqual(
            cm.exception.args[0],
            "Just testing error handling when processing is broken",
        )
        self.runner = None

    def test_watch_for_errors_exits_without_raising_after_timeout(self):
        # Construct system and start runner
        system = System(
            pipes=[
                [
                    BankAccounts,
                    EmailProcess,
                ],
            ]
        )
        self.start_runner(system)

        # Watch for error with a timeout. Check returns False.
        self.assertFalse(self.runner.watch_for_errors(timeout=0.0))

    def test_stops_if_app_processing_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )

        self.start_runner(system)

        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check watch_for_errors() raises exception.
        with self.assertRaises(EventProcessingError) as cm:
            self.runner.watch_for_errors(timeout=1)
        self.assertIn(
            "Just testing error handling when processing is broken",
            cm.exception.args[0],
        )
        self.runner = None


class TestMultiThreadedRunnerWithSQLiteFileBased(TestMultiThreadedRunner):
    def setUp(self):
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        uris = tmpfile_uris()
        os.environ[f"{BankAccounts.name.upper()}_SQLITE_DBNAME"] = next(uris)
        os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"] = next(uris)
        os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"] = next(uris)
        os.environ[f"MY{EmailProcess.name.upper()}_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPROCESSING_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENCONVERTING_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPULLING_SQLITE_DBNAME"] = next(uris)
        os.environ["COMMANDS_SQLITE_DBNAME"] = next(uris)
        os.environ["RESULTS_SQLITE_DBNAME"] = next(uris)

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ[f"{BankAccounts.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"MY{EmailProcess.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"]
        del os.environ["BROKENPROCESSING_SQLITE_DBNAME"]
        del os.environ["BROKENCONVERTING_SQLITE_DBNAME"]
        del os.environ["BROKENPULLING_SQLITE_DBNAME"]
        del os.environ["COMMANDS_SQLITE_DBNAME"]
        del os.environ["RESULTS_SQLITE_DBNAME"]
        super().tearDown()


class TestMultiThreadedRunnerWithSQLiteInMemory(TestMultiThreadedRunner):
    def setUp(self):
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ[
            f"{BankAccounts.name.upper()}_SQLITE_DBNAME"
        ] = f"file:{BankAccounts.name.lower()}?mode=memory&cache=shared"
        os.environ[
            f"{EmailProcess.name.upper()}_SQLITE_DBNAME"
        ] = f"file:{EmailProcess.name.lower()}?mode=memory&cache=shared"
        os.environ[
            f"MY{EmailProcess.name.upper()}_SQLITE_DBNAME"
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
        os.environ["COMMANDS_SQLITE_DBNAME"] = "file:commands?mode=memory&cache=shared"
        os.environ["RESULTS_SQLITE_DBNAME"] = "file:results?mode=memory&cache=shared"

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ[f"{BankAccounts.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"MY{EmailProcess.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"]
        del os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"]
        del os.environ["BROKENPROCESSING_SQLITE_DBNAME"]
        del os.environ["BROKENCONVERTING_SQLITE_DBNAME"]
        del os.environ["BROKENPULLING_SQLITE_DBNAME"]
        del os.environ["COMMANDS_SQLITE_DBNAME"]
        del os.environ["RESULTS_SQLITE_DBNAME"]
        super().tearDown()


class TestMultiThreadedRunnerWithPostgres(TestMultiThreadedRunner):
    def setUp(self):
        super().setUp()
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
        drop_postgres_table(db, "brokenprocessing_tracking")
        drop_postgres_table(db, "brokenconverting_events")
        drop_postgres_table(db, "brokenconverting_tracking")
        drop_postgres_table(db, "brokenpulling_events")
        drop_postgres_table(db, "brokenpulling_tracking")
        drop_postgres_table(db, "commands_events")
        drop_postgres_table(db, "commands_tracking")
        drop_postgres_table(db, "results_events")
        drop_postgres_table(db, "results_tracking")

        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"

    def tearDown(self):
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        super().tearDown()

    def wait_for_runner(self):
        sleep(0.6)
        super().wait_for_runner()


class TestNewMultiThreadedRunner(TestMultiThreadedRunner):
    runner_class = NewMultiThreadedRunner

    class BrokenPulling(EmailProcess):
        def pull_notifications(
            self, leader_name: str, start: int, stop: Optional[int] = None
        ) -> Iterable[List[Notification]]:
            raise ProgrammingError("Just testing error handling when pulling is broken")

    class BrokenConverting(EmailProcess):
        def convert_notifications(
            self, leader_name: str, notifications: Iterable[Notification]
        ) -> List[ProcessingJob]:
            raise ProgrammingError(
                "Just testing error handling when converting is broken"
            )

    # This duplicates test method above.
    def test_ignores_recording_event_if_seen_subsequent(self):
        system = System(pipes=[[BankAccounts, EmailProcess]])
        self.start_runner(system)

        accounts = self.runner.get(BankAccounts)
        email_process = self.runner.get(EmailProcess)

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        self.wait_for_runner()

        self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

        # Reset this to break sequence.
        accounts.previous_max_notification_id -= 1

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        self.wait_for_runner()

        self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

    def test_queue_task_done_is_called(self):
        system = System(pipes=[[BankAccounts, EmailProcess]])
        self.start_runner(system)

        accounts = self.runner.get(BankAccounts)
        email_process1 = self.runner.get(EmailProcess)

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )
        sleep(0.1)
        self.assertEqual(len(email_process1.notification_log["1,10"].items), 1)

        for thread in self.runner.all_threads:
            if isinstance(thread, ConvertingThread):
                self.assertEqual(thread.converting_queue.unfinished_tasks, 0)
                self.assertEqual(thread.processing_queue.unfinished_tasks, 0)

    def test_stop_raises_if_notification_converting_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestNewMultiThreadedRunner.BrokenConverting,
                ],
            ]
        )

        # Create runner.
        self.runner = self.runner_class(system)

        # Create some notifications.
        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start runner.
        self.runner.start()

        # Trigger pulling of notifications.
        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Wait for runner to error.
        self.assertTrue(self.runner.has_errored.wait(timeout=1000))

        # Check stop() raises exception.
        with self.assertRaises(NotificationConvertingError) as cm:
            self.runner.stop()
        self.assertIn(
            "Just testing error handling when converting is broken",
            cm.exception.args[0],
        )
        self.runner = None

    def test_stop_raises_if_notification_pulling_is_broken(self):
        system = System(
            pipes=[
                [
                    BankAccounts,
                    TestNewMultiThreadedRunner.BrokenPulling,
                ],
            ]
        )
        # Create runner.
        self.runner = self.runner_class(system)

        # Create some notifications.
        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start runner.
        self.runner.start()

        # Trigger pulling of notifications.
        accounts = self.runner.get(BankAccounts)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Wait for runner to error.
        self.assertTrue(self.runner.has_errored.wait(timeout=1))

        # Check stop() raises exception.
        with self.assertRaises(NotificationPullingError) as cm:
            self.runner.stop()
        self.assertIn(
            "Just testing error handling when pulling is broken",
            cm.exception.args[0],
        )
        self.runner = None

    def wait_for_runner(self):
        sleep(0.1)
        try:
            self.runner.reraise_thread_errors()
        except Exception as e:
            self.runner = None
            raise Exception("Runner errored: " + str(e)) from e


del RunnerTestCase
