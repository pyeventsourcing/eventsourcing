from __future__ import annotations

import threading
import warnings
import weakref
from threading import Event
from time import sleep
from typing import TYPE_CHECKING, Any, ClassVar, override
from unittest import TestCase
from uuid import uuid4

from eventsourcing.errors import WaitInterruptedError
from eventsourcing.msgspec import AggregatesApplication, Transcoder
from eventsourcing.persistence import StreamEventMapper, TrackingRecorder
from eventsourcing.projection import (
    ReadModelPolicy,
    ReadModelRunner,
)
from eventsourcing.tests.projection import (
    SpannerThrown,
    SpannerThrownError,
    StudentAggregate,
    StudentAnalyticsPolicy,
    StudentAnalyticsReadModel,
    StudentNameChanged,
)
from eventsourcing.utils import get_topic
from tests.projection_tests.test_projection_with_popo import (
    POPOStudentAnalyticsReadModel,
)

if TYPE_CHECKING:
    from eventsourcing.persistence import Tracking


class TestReadModelRunner(TestCase):
    env: ClassVar[dict[str, str]] = {
        "MAPPER_TOPIC": get_topic(StreamEventMapper),
        "TRANSCODER_TOPIC": get_topic(Transcoder),
        "PERSISTENCE_MODULE": "eventsourcing.popo",
    }

    def test_runner(self) -> None:
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )

        self.assertFalse(runner.is_interrupted.is_set())

        aggregate = StudentAggregate(student_id=str(uuid4()))
        aggregate.change_name()
        aggregate.change_name()
        notification_id = runner.upstream.save(aggregate)

        runner.wait(notification_id)
        self.assertEqual(runner.read_model.get_student_registered_counter(), 1)
        self.assertEqual(runner.read_model.get_student_name_changed_counter(), 2)

        aggregate = StudentAggregate(student_id=str(uuid4()))
        aggregate.change_name()
        aggregate.change_name()
        notification_id = runner.upstream.save(aggregate)

        runner.wait(notification_id)
        self.assertEqual(runner.read_model.get_student_registered_counter(), 2)
        self.assertEqual(runner.read_model.get_student_name_changed_counter(), 4)

        runner.run_forever(timeout=0.1)

        with self.assertRaises(TimeoutError):
            runner.wait(
                notification_id=(runner.upstream.recorder.max_notification_id() or 0)
                + 1,
                timeout=0.1,
            )

        aggregate.trigger_event(SpannerThrown, student_id=aggregate.id)
        runner.upstream.save(aggregate)

        with self.assertRaises(SpannerThrownError):
            runner.run_forever()

        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        aggregate = StudentAggregate(student_id=str(uuid4()))
        aggregate.trigger_event(SpannerThrown, student_id=aggregate.id)
        runner.upstream.save(aggregate)

        with self.assertRaises(SpannerThrownError):
            runner.wait(runner.upstream.recorder.max_notification_id())

        self.assertTrue(runner.is_interrupted.is_set())

    def test_runner_with_topics(self) -> None:
        class StudentAnalyticsPolicyWithTopics(StudentAnalyticsPolicy):
            topics = (get_topic(StudentNameChanged),)

        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicyWithTopics,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )

        app = runner.upstream
        aggregate = StudentAggregate(student_id=str(uuid4()))
        aggregate.change_name()
        aggregate.change_name()
        notification_id = app.save(aggregate)

        runner.wait(notification_id)
        # Should be zero because we didn't include Aggregate.Created topic.
        self.assertEqual(runner.read_model.get_student_registered_counter(), 0)
        # Should be two because we did include Student.NameChanged topic.
        self.assertEqual(runner.read_model.get_student_name_changed_counter(), 2)

    def test_runner_stop(self) -> None:
        # Call stop() before run_forever().
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        runner.stop()
        runner.run_forever()

        # Call stop() before wait().
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        runner.stop()
        runner.wait(10000)

        exception_raised = Event()
        thread_started = Event()
        errors: list[Exception] = []

        def call_runforever(
            r: ReadModelRunner[
                AggregatesApplication,
                StudentAnalyticsPolicy,
                StudentAnalyticsReadModel,
            ],
        ) -> None:
            errors.clear()
            exception_raised.clear()
            thread_started.set()
            try:
                r.run_forever()
            except Exception as e:
                errors.append(e)
                exception_raised.set()
            finally:
                thread_started.clear()

        def call_wait(
            r: ReadModelRunner[
                AggregatesApplication,
                StudentAnalyticsPolicy,
                StudentAnalyticsReadModel,
            ],
        ) -> None:
            errors.clear()
            exception_raised.clear()
            thread_started.set()
            try:
                r.wait(1)
            except Exception as e:
                errors.append(e)
                exception_raised.set()
            finally:
                thread_started.set()

        # Call stop() after run_forever().
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        thread = threading.Thread(target=call_runforever, args=(runner,))
        thread.start()
        thread_started.wait()
        sleep(0.1)
        runner.stop()
        thread.join()
        if exception_raised.is_set():
            raise AssertionError from errors[0]

        # Call stop() after wait().
        ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        thread = threading.Thread(target=call_wait, args=(runner,))
        thread.start()
        thread_started.wait()
        sleep(0.1)
        runner.stop()
        thread.join()
        if exception_raised.is_set():
            raise AssertionError from errors[0]

    def test_enter_returns_runner(self) -> None:
        with ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        ) as runner:
            self.assertIsInstance(runner, ReadModelRunner)

    def test_exit_stops_runner(self) -> None:
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=StudentAnalyticsPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        self.assertFalse(runner.is_interrupted.is_set())
        with runner:
            self.assertFalse(runner.is_interrupted.is_set())
        self.assertTrue(runner.is_interrupted.is_set())

    def test_exit_doesnt_suppress_error(self) -> None:
        class TestError(Exception):
            pass

        with (
            self.assertRaises(TestError),
            ReadModelRunner(
                upstream_class=AggregatesApplication,
                policy_class=StudentAnalyticsPolicy,
                read_model_class=POPOStudentAnalyticsReadModel,
                env=self.env,
            ),
        ):
            raise TestError

    def test_exit_raises_processing_error(self) -> None:
        with (
            self.assertRaises(BrokenPolicyError),
            ReadModelRunner(
                upstream_class=AggregatesApplication,
                policy_class=BrokenReadModelPolicy,
                read_model_class=POPOStudentAnalyticsReadModel,
                env=self.env,
            ) as runner,
        ):
            # Write an event.
            runner.upstream.save(StudentAggregate(student_id=str(uuid4())))
            runner.is_interrupted.wait()

    def test_warning_error_not_assigned_to_deleted_runner(self) -> None:

        # Construct a runner.
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=BrokenReadModelPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )

        # Write an event.
        runner.upstream.save(StudentAggregate(student_id=str(uuid4())))

        # Error should be assigned to the runner.
        with self.assertRaises(BrokenPolicyError):
            runner.run_forever()

        # Write another event.
        runner.upstream.save(StudentAggregate(student_id=str(uuid4())))

        # Get another application subscription
        subscription = runner.upstream.application_subscription()

        # Get a reference to the projection.
        projection = runner.policy

        # Construct another threading.Event.
        has_error = Event()

        # Get another weakref to the runner.
        ref = weakref.ref(runner)

        # Delete the runner object.
        del runner

        # Check the weakref returns None.
        self.assertIsNone(ref())

        # Call _process_events_loop and catch warning.
        with warnings.catch_warnings(record=True) as w:
            ReadModelRunner[
                AggregatesApplication, ReadModelPolicy[Any, Any], TrackingRecorder
            ]._consumer_loop(
                subscription,
                projection,
                has_error,
                ref,
            )

            self.assertEqual(1, len(w))
            self.assertIs(w[-1].category, RuntimeWarning)
            last_message = w[-1].message
            self.assertIsInstance(last_message, RuntimeWarning)
            self.assertIn(
                "Event consumer was deleted before error could be assigned:",
                str(last_message),
            )

        # Check the event was set anyway.
        self.assertTrue(has_error.is_set())

    def test_wait_raises_wait_interrupted_error(self) -> None:
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=VerySlowReadModelPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        runner.upstream.save(StudentAggregate(student_id=str(uuid4())))
        with self.assertRaises(WaitInterruptedError):
            sleep(0.5)
            runner.is_interrupted.set()
            runner.wait(1000, timeout=10)

        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=VerySlowReadModelPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        runner.upstream.save(StudentAggregate(student_id=str(uuid4())))
        with self.assertRaises(WaitInterruptedError), runner:
            sleep(0.5)
            runner.is_interrupted.set()
            runner.wait(1000, timeout=10)

    def test_wait_raises_timeout_error(self) -> None:
        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=VerySlowReadModelPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        runner.upstream.save(StudentAggregate(student_id=str(uuid4())))
        with self.assertRaises(TimeoutError):
            sleep(0.5)
            runner.wait(1000, timeout=0.1)

        runner = ReadModelRunner(
            upstream_class=AggregatesApplication,
            policy_class=VerySlowReadModelPolicy,
            read_model_class=POPOStudentAnalyticsReadModel,
            env=self.env,
        )
        runner.upstream.save(StudentAggregate(student_id=str(uuid4())))
        with self.assertRaises(TimeoutError), runner:
            sleep(0.5)
            runner.wait(1000, timeout=0.1)


class BrokenPolicyError(Exception):
    pass


# Define a policy that raises an exception.
class BrokenReadModelPolicy(ReadModelPolicy[TrackingRecorder, Any]):
    @override
    def process_event(self, envelope: Any, tracking: Tracking) -> None:
        raise BrokenPolicyError


# Define a policy that stalls.
class VerySlowReadModelPolicy(ReadModelPolicy[TrackingRecorder, Any]):
    @override
    def process_event(self, envelope: Any, tracking: Tracking) -> None:
        sleep(2)
