from __future__ import annotations

import os
import shlex
import subprocess
from queue import Queue
from threading import Event
from time import sleep
from typing import TYPE_CHECKING, Any
from unittest.case import TestCase
from unittest.mock import MagicMock

from typing_extensions import TypeVar

from eventsourcing.application import ProcessingEvent  # noqa: TC001
from eventsourcing.dataclasses.application import DataclassApplication
from eventsourcing.dataclasses.immutable import DataclassDecision
from eventsourcing.dataclasses.mutable import DataclassAggregate
from eventsourcing.domain_new import (
    Aggregate,
    AggregateEvent,
    EventEnvelope,
    TDecision,
    triggers,
)
from eventsourcing.errors import ProgrammingError
from eventsourcing.msgspec.transcoder import MsgspecTranscoder
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
    RecordingEvent,
    Runner,
    RunnerAlreadyStartedError,
    SingleThreadedRunner,
    System,
)
from eventsourcing.tests.application import BankAccountsWithPydantic
from eventsourcing.tests.persistence import tmpfile_uris
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import EnvType, clear_topic_cache, get_topic
from tests.application_tests.test_processapplication import EmailProcess

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from eventsourcing.persistence import Notification, Tracking, Transcoder


class EmailProcess2(EmailProcess):
    pass


TRunner = TypeVar(
    "TRunner",
    bound=Runner[Any],
    # default=SingleThreadedRunner[TDecision] | NewSingleThreadedRunner[TDecision],
)


class Command(DataclassAggregate):
    class Created(DataclassDecision):
        text: str

    class Done(DataclassDecision):
        output: str
        error: str

    @triggers(Created)
    def __init__(self, text: str):
        self.text = text
        self.output: str | None = None
        self.error: str | None = None

    @triggers(Done)
    def done(self, output: str, error: str) -> None:
        self.output = output
        self.error = error


class Result(Aggregate[DataclassDecision]):
    class Created(DataclassDecision):
        command_id: str
        output: str
        error: str

    @triggers(Created)
    def __init__(self, command_id: str, output: str, error: str):
        self.command_id = command_id
        self.output = output
        self.error = error


class TestSingleThreadedRunner(TestCase):
    def construct_runner(
        self, system: System, env: EnvType | None = None
    ) -> Runner[Any]:
        return SingleThreadedRunner(system, env)

    def wait_for_runner(self, runner: TRunner) -> None:
        pass

    def test_runner_constructed_with_env_has_apps_with_env(self) -> None:
        system = System(pipes=[[BankAccountsWithPydantic, EmailProcess]])
        env = {"MY_ENV_VAR": "my_env_val"}
        with self.construct_runner(system, env) as runner:

            # Check leaders get the environment.
            bank_accounts = runner.get(BankAccountsWithPydantic)
            self.assertEqual(bank_accounts.env.get("MY_ENV_VAR"), "my_env_val")

            # Check followers get the environment.
            email_process = runner.get(EmailProcess)
            self.assertEqual(email_process.env.get("MY_ENV_VAR"), "my_env_val")

        # Check singles get the environment.
        system = System(pipes=[[BankAccountsWithPydantic]])
        env = {"MY_ENV_VAR": "my_env_val"}
        with self.construct_runner(system, env) as runner:
            bank_accounts = runner.get(BankAccountsWithPydantic)
            self.assertEqual(bank_accounts.env.get("MY_ENV_VAR"), "my_env_val")

    def test_starts_with_single_app(self) -> None:
        with self.construct_runner(
            System(pipes=[[BankAccountsWithPydantic]])
        ) as runner:
            app = runner.get(BankAccountsWithPydantic)
            self.assertIsInstance(app, BankAccountsWithPydantic)

    def test_calling_start_twice_raises_error(self) -> None:
        with (
            self.construct_runner(System(pipes=[[BankAccountsWithPydantic]])) as runner,
            self.assertRaises(RunnerAlreadyStartedError),
        ):
            runner.start()

    def test_system_with_one_edge(self) -> None:
        system = System(pipes=[[BankAccountsWithPydantic, EmailProcess]])
        with self.construct_runner(system) as runner:
            accounts = runner.get(BankAccountsWithPydantic)
            email_process = runner.get(EmailProcess)

            section = email_process.notification_log["1,5"]
            self.assertEqual(len(section.items), 0, section.items)

            for _ in range(10):
                accounts.open_account(
                    full_name="Alice",
                    email_address="alice@example.com",
                )

            self.wait_for_runner(runner)

            section = email_process.notification_log["1,10"]
            self.assertEqual(len(section.items), 10)

    def test_system_with_two_edges(self) -> None:
        clear_topic_cache()

        # Construct system and runner.
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    EmailProcess,
                ],
                [
                    BankAccountsWithPydantic,
                    EmailProcess2,
                ],
            ]
        )
        with self.construct_runner(system) as runner:

            # Get apps.
            accounts = runner.get(BankAccountsWithPydantic)
            email_process1 = runner.get(EmailProcess)
            email_process2 = runner.get(EmailProcess2)

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
            self.wait_for_runner(runner)
            section = email_process1.notification_log["1,10"]
            self.assertEqual(len(section.items), 10)
            section = email_process2.notification_log["1,10"]
            self.assertEqual(len(section.items), 10)

    def test_system_with_processing_loop(self) -> None:
        class Commands(DataclassApplication, ProcessApplication[DataclassDecision]):
            def create_command(self, text: str) -> str:
                command = Command(text=text)
                self.save(command)
                return command.id

            def policy(
                self,
                envelope: EventEnvelope[DataclassDecision],
                processing_event: ProcessingEvent[DataclassDecision],
            ) -> None:
                match envelope.decision:
                    case Result.Created(
                        command_id=command_id, output=output, error=error
                    ):

                        command = self.repository.get(command_id, Command)
                        command.done(
                            output=output,
                            error=error,
                        )
                        processing_event.collect_events(command)

            def get_result(self, command_id: str) -> tuple[str | None, str | None]:
                command = self.repository.get(command_id, Command)
                return command.output, command.error

        class Results(DataclassApplication, ProcessApplication[DataclassDecision]):
            def policy(
                self,
                envelope: AggregateEvent[DataclassDecision],
                processing_event: ProcessingEvent,
            ) -> None:
                match envelope.decision:
                    case Command.Created(text=text):
                        try:
                            openargs = shlex.split(text)
                            output = subprocess.check_output(openargs)  # noqa: S603
                            error = ""
                        except Exception as e:
                            error = str(e)
                            output = b""
                        result = Result(
                            command_id=envelope.originator_id,
                            output=output.decode("utf8"),
                            error=error,
                        )
                        processing_event.collect_events(result)

        system = System([[Commands, Results, Commands]])
        with self.construct_runner(system) as runner:

            commands = runner.get(Commands)
            command_id1 = commands.create_command("echo 'Hello World'")
            command_id2 = commands.create_command("notacommand")

            self.wait_for_runner(runner)

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
            assert error is not None
            self.assertIn("No such file or directory: 'notacommand'", error)

    def test_catches_up_with_outstanding_notifications(self) -> None:
        # Construct system and runner.
        system = System(pipes=[[BankAccountsWithPydantic, EmailProcess]])
        runner = self.construct_runner(system)

        # Get apps.
        accounts = runner.get(BankAccountsWithPydantic)
        email_process1 = runner.get(EmailProcess)

        # Create an event.
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check we processed nothing.
        self.assertEqual(
            email_process1.recorder.max_tracking_id("BankAccountsWithPydantic"), None
        )

        # Start the runner.
        with runner:

            # Create another event.
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

            # Check we processed two events.
            self.wait_for_runner(runner)
            self.assertEqual(
                email_process1.recorder.max_tracking_id("BankAccountsWithPydantic"), 2
            )

    def test_filters_notifications_by_topics(self) -> None:
        class MyEmailProcess(EmailProcess):
            topics = (get_topic(AggregateEvent),)

        system = System(pipes=[[BankAccountsWithPydantic, MyEmailProcess]])
        runner = self.construct_runner(system)

        accounts = runner.get(BankAccountsWithPydantic)
        email_process = runner.get(MyEmailProcess)

        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        with runner:
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )
            self.wait_for_runner(runner)
            self.assertEqual(len(email_process.notification_log["1,10"].items), 0)


#
# class SingleThreadedRunnerFollowersOrderingMixin:
#     """Followers ordering tests for single-threaded runners."""
#
#     def test_followers_are_prompted_in_declaration_order(self) -> None:
#         """Validate the order in which followers are prompted by the runner.
#
#         This test can, by nature, show some flakiness. That is, we can
#         see false negatives at times when a random ordering would match
#         the expected ordering. We mitigate this problem by increasing
#         the number of followers to be ordered.
#         """
#         clear_topic_cache()
#         app_calls = []
#
#         class NameLogger(EmailProcess):
#             def policy(self, _, __):
#                 app_calls.append(self.__class__.__name__)
#
#         def make_name_logger(n: int) -> type:
#             return type(f"NameLogger{n}", (NameLogger,), {})
#
#         # Construct system and runner.
#         system = System(
#             pipes=[
#                 [BankAccounts, make_name_logger(3)],
#                 [BankAccounts, make_name_logger(4)],
#                 [BankAccounts, make_name_logger(1)],
#                 [BankAccounts, make_name_logger(5)],
#                 [BankAccounts, make_name_logger(2)],
#             ]
#         )
#         self.start_runner(system)
#
#         # Create an event.
#         runner.get(BankAccounts).open_account(
#             full_name="Alice",
#             email_address="alice@example.com",
#         )
#
#         self.wait_for_runner(runner)
#
#         # Check the applications' policy were called in the right order.
#         self.assertEqual(
#           app_calls,
#           ["NameLogger3", "NameLogger4", "NameLogger1", "NameLogger5", "NameLogger2"],
#         )
#
#
# class TestSingleThreadedRunner(
#     RunnerTestCase[SingleThreadedRunner], SingleThreadedRunnerFollowersOrderingMixin
# ):
#     runner_class = SingleThreadedRunner
#
#
class TestNewSingleThreadedRunner(TestSingleThreadedRunner):

    def construct_runner(
        self, system: System, env: EnvType | None = None
    ) -> NewSingleThreadedRunner:
        return NewSingleThreadedRunner(system=system, env=env)

    def test_ignores_recording_event_if_seen_subsequent(self) -> None:
        system = System(pipes=[[BankAccountsWithPydantic, EmailProcess]])
        with self.construct_runner(system) as runner:

            accounts = runner.get(BankAccountsWithPydantic)
            email_process = runner.get(EmailProcess)

            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )
            self.wait_for_runner(runner)

            self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

            # Reset this to break sequence.
            accounts.previous_max_notification_id -= 1  # type: ignore[attr-defined]

            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )
            self.wait_for_runner(runner)

            self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

    def test_received_notifications_accumulate(self) -> None:
        system = System([[BankAccountsWithPydantic, EmailProcess]])
        with self.construct_runner(system) as runner:

            accounts = runner.get(BankAccountsWithPydantic)
            # Need to get the lock, so that they aren't cleared.
            with runner._processing_lock:
                accounts.open_account("Alice", "alice@example.com")
                self.assertEqual(len(runner._recording_events_received), 1)
                accounts.open_account("Bob", "bob@example.com")
                self.assertEqual(len(runner._recording_events_received), 2)


class TestPullingThread(TestCase):
    def test_receive_recording_event_does_not_block(self) -> None:
        thread = PullingThread(
            converting_queue=Queue(),
            follower=MagicMock(),
            leader_name="BankAccountsWithPydantic",
            has_errored=Event(),
        )
        thread.recording_event_queue.maxsize = 1
        self.assertEqual(thread.recording_event_queue.qsize(), 0)
        thread.receive_recording_event(
            RecordingEvent(
                application_name="BankAccountsWithPydantic",
                recordings=[],
                previous_max_notification_id=None,
            )
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 1)
        self.assertFalse(thread.overflow_event.is_set())
        thread.receive_recording_event(
            RecordingEvent(
                application_name="BankAccountsWithPydantic",
                recordings=[],
                previous_max_notification_id=1,
            )
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 1)
        self.assertTrue(thread.overflow_event.is_set())

    def test_stops_because_stopping_event_is_set(self) -> None:
        thread = PullingThread(
            converting_queue=Queue(),
            follower=MagicMock(),
            leader_name="BankAccountsWithPydantic",
            has_errored=Event(),
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 0)
        thread.receive_recording_event(
            RecordingEvent(
                application_name="BankAccountsWithPydantic",
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

    def test_stops_because_recording_event_queue_was_poisoned(self) -> None:
        thread = PullingThread(
            converting_queue=Queue(),
            follower=MagicMock(),
            leader_name="BankAccountsWithPydantic",
            has_errored=Event(),
        )
        self.assertEqual(thread.recording_event_queue.qsize(), 0)
        thread.start()
        thread.stop()  # Poison queue.
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(thread.recording_event_queue.qsize(), 0)


class TestMultiThreadedRunner(TestSingleThreadedRunner):
    def construct_runner(
        self, system: System, env: EnvType | None = None
    ) -> MultiThreadedRunner | NewMultiThreadedRunner:
        return MultiThreadedRunner(system=system, env=env)

    def test_ignores_recording_event_if_seen_subsequent(self) -> None:
        # Skipping this because this runner doesn't take
        # notice of attribute previous_max_notification_id.
        pass

    class DeliberateError(Exception):
        pass

    def wait_for_runner(
        self,
        runner: MultiThreadedRunner[TDecision] | NewMultiThreadedRunner[TDecision],
    ) -> None:
        sleep(0.3)
        runner.reraise_thread_errors()

    class BrokenInitialisation(EmailProcess):
        def __init__(self, *_: Any, **__: Any) -> None:
            msg = "Just testing error handling when initialisation is broken"
            raise TestMultiThreadedRunner.DeliberateError(msg)

    class BrokenProcessing(EmailProcess):
        def process_event(
            self, envelope: AggregateEvent[DataclassDecision], tracking: Tracking
        ) -> None:
            msg = "Just testing error handling when processing is broken"
            raise TestMultiThreadedRunner.DeliberateError(msg)

    def test_stops_if_app_initialisation_is_broken(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    TestMultiThreadedRunner.BrokenInitialisation,
                ],
            ]
        )

        with self.assertRaises(TestMultiThreadedRunner.DeliberateError) as cm:
            self.construct_runner(system)

        self.assertEqual(
            cm.exception.args[0],
            "Just testing error handling when initialisation is broken",
        )

    def test_stop_raises_if_event_processing_is_broken(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )
        # Check stop() raises exception.
        with (
            self.assertRaises(EventProcessingError) as cm,
            self.construct_runner(system) as runner,
        ):

            accounts = runner.get(BankAccountsWithPydantic)
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

            # Wait for runner to stop.
            self.assertTrue(runner.has_errored.wait(timeout=1))

        self.assertIn(
            "Just testing error handling when processing is broken",
            cm.exception.args[0],
        )

    def test_watch_for_errors_raises_if_runner_errors(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )
        # Create runner.
        runner = self.construct_runner(system)

        # Create some notifications.
        accounts = runner.get(BankAccountsWithPydantic)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start runner.
        with self.assertRaises(EventProcessingError) as cm, runner:

            # Trigger pulling of notifications.
            accounts = runner.get(BankAccountsWithPydantic)
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

            # Check watch_for_errors() raises exception.
            runner.watch_for_errors(timeout=1)

        self.assertEqual(
            cm.exception.args[0],
            "Just testing error handling when processing is broken",
        )

    def test_watch_for_errors_exits_without_raising_after_timeout(self) -> None:
        # Construct system and start runner
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    EmailProcess,
                ],
            ]
        )
        with self.construct_runner(system) as runner:

            # Watch for error with a timeout. Check returns False.
            self.assertFalse(runner.watch_for_errors(timeout=0.1))

    def test_stops_if_app_processing_is_broken(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    TestMultiThreadedRunner.BrokenProcessing,
                ],
            ]
        )

        with (
            self.assertRaises(EventProcessingError) as cm,
            self.construct_runner(system) as runner,
        ):

            accounts = runner.get(BankAccountsWithPydantic)
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

            # Check watch_for_errors() raises exception.
            runner.watch_for_errors(timeout=1)

        self.assertIn(
            "Just testing error handling when processing is broken",
            cm.exception.args[0],
        )


class TestMultiThreadedRunnerWithSQLiteFileBased(TestMultiThreadedRunner):
    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        uris = tmpfile_uris()
        os.environ[f"{BankAccountsWithPydantic.name.upper()}_SQLITE_DBNAME"] = next(
            uris
        )
        os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"] = next(uris)
        os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"] = next(uris)
        os.environ[f"MY{EmailProcess.name.upper()}_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPROCESSING_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENCONVERTING_SQLITE_DBNAME"] = next(uris)
        os.environ["BROKENPULLING_SQLITE_DBNAME"] = next(uris)
        os.environ["COMMANDS_SQLITE_DBNAME"] = next(uris)
        os.environ["RESULTS_SQLITE_DBNAME"] = next(uris)

    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ[f"{BankAccountsWithPydantic.name.upper()}_SQLITE_DBNAME"]
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
    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
        os.environ[f"{BankAccountsWithPydantic.name.upper()}_SQLITE_DBNAME"] = (
            f"file:{BankAccountsWithPydantic.name.lower()}?mode=memory&cache=shared"
        )
        os.environ[f"{EmailProcess.name.upper()}_SQLITE_DBNAME"] = (
            f"file:{EmailProcess.name.lower()}?mode=memory&cache=shared"
        )
        os.environ[f"MY{EmailProcess.name.upper()}_SQLITE_DBNAME"] = (
            f"file:{EmailProcess.name.lower()}?mode=memory&cache=shared"
        )
        os.environ[f"{EmailProcess.name.upper()}2_SQLITE_DBNAME"] = (
            f"file:{EmailProcess.name.lower()}2?mode=memory&cache=shared"
        )
        os.environ["BROKENPROCESSING_SQLITE_DBNAME"] = (
            "file:brokenprocessing?mode=memory&cache=shared"
        )
        os.environ["BROKENCONVERTING_SQLITE_DBNAME"] = (
            "file:brokenconverting?mode=memory&cache=shared"
        )
        os.environ["BROKENPULLING_SQLITE_DBNAME"] = (
            "file:brokenprocessing?mode=memory&cache=shared"
        )
        os.environ["COMMANDS_SQLITE_DBNAME"] = "file:commands?mode=memory&cache=shared"
        os.environ["RESULTS_SQLITE_DBNAME"] = "file:results?mode=memory&cache=shared"

    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ[f"{BankAccountsWithPydantic.name.upper()}_SQLITE_DBNAME"]
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
    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"  # noqa: S105
        drop_tables()

    def tearDown(self) -> None:
        drop_tables()
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        super().tearDown()

    def wait_for_runner(
        self,
        runner: MultiThreadedRunner[TDecision] | NewMultiThreadedRunner[TDecision],
    ) -> None:
        sleep(0.6)
        super().wait_for_runner(runner)


class TestNewMultiThreadedRunner(TestMultiThreadedRunner):

    def construct_runner(
        self, system: System, env: EnvType | None = None
    ) -> NewMultiThreadedRunner:
        return NewMultiThreadedRunner(system=system, env=env)

    class BrokenPulling(EmailProcess):
        def pull_notifications(
            self,
            leader_name: str,
            start: int | None,
            stop: int | None = None,
            *,
            inclusive_of_start: bool = True,
        ) -> Iterator[list[Notification]]:
            msg = "Just testing error handling when pulling is broken"
            raise ProgrammingError(msg)

    class BrokenConverting(EmailProcess):
        def convert_notifications(
            self, leader_name: str, notifications: Iterable[Notification]
        ) -> list[ProcessingJob]:
            msg = "Just testing error handling when converting is broken"
            raise ProgrammingError(msg)

    # This duplicates test method above.
    def test_ignores_recording_event_if_seen_subsequent(self) -> None:
        system = System(pipes=[[BankAccountsWithPydantic, EmailProcess]])

        with self.construct_runner(system) as runner:
            accounts = runner.get(BankAccountsWithPydantic)
            email_process = runner.get(EmailProcess)

            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )
            self.wait_for_runner(runner)

            self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

            # Reset this to break sequence.
            accounts.previous_max_notification_id -= 1  # type: ignore[attr-defined]

            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )
            self.wait_for_runner(runner)

            self.assertEqual(len(email_process.notification_log["1,10"].items), 1)

    def test_queue_task_done_is_called(self) -> None:
        system = System(pipes=[[BankAccountsWithPydantic, EmailProcess]])

        with self.construct_runner(system) as runner:

            accounts = runner.get(BankAccountsWithPydantic)
            email_process1 = runner.get(EmailProcess)

            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )
            sleep(0.1)
            self.assertEqual(len(email_process1.notification_log["1,10"].items), 1)

            assert isinstance(runner, NewMultiThreadedRunner), runner  # for mypy,
            for thread in runner.all_threads:
                if isinstance(thread, ConvertingThread):
                    self.assertEqual(thread.converting_queue.unfinished_tasks, 0)
                    self.assertEqual(thread.processing_queue.unfinished_tasks, 0)

    def test_stop_raises_if_notification_converting_is_broken(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    TestNewMultiThreadedRunner.BrokenConverting,
                ],
            ]
        )

        # Construct runner.
        runner = self.construct_runner(system)

        # Create some notifications.
        accounts = runner.get(BankAccountsWithPydantic)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start runner.
        with self.assertRaises(NotificationConvertingError) as cm, runner:

            # Trigger pulling of notifications.
            accounts = runner.get(BankAccountsWithPydantic)
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

            # Wait for runner to error.
            self.assertTrue(runner.has_errored.wait(timeout=1000))

        self.assertIn(
            "Just testing error handling when converting is broken",
            cm.exception.args[0],
        )

    def test_stop_raises_if_notification_pulling_is_broken(self) -> None:
        system = System(
            pipes=[
                [
                    BankAccountsWithPydantic,
                    TestNewMultiThreadedRunner.BrokenPulling,
                ],
            ]
        )
        # Create runner.

        runner = self.construct_runner(system)

        # Create some notifications.
        accounts = runner.get(BankAccountsWithPydantic)
        accounts.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Start runner.
        with self.assertRaises(NotificationPullingError) as cm, runner:

            # Trigger pulling of notifications.
            accounts = runner.get(BankAccountsWithPydantic)
            accounts.open_account(
                full_name="Alice",
                email_address="alice@example.com",
            )

            # Wait for runner to error.
            self.assertTrue(runner.has_errored.wait(timeout=1))

        self.assertIn(
            "Just testing error handling when pulling is broken",
            cm.exception.args[0],
        )
