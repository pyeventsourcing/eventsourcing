from __future__ import annotations

import threading
import warnings
import weakref
from threading import Event
from time import sleep
from typing import TYPE_CHECKING, Any
from unittest import TestCase

from eventsourcing.application import Application
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import WaitInterruptedError
from eventsourcing.projection import (
    ApplicationSubscription,
    Projection,
    ProjectionRunner,
)
from eventsourcing.utils import get_topic
from tests.projection_tests.test_projection import (
    AggregateEventCountersProjection,
    POPOEventCounters,
    SpannerThrown,
    SpannerThrownError,
)

if TYPE_CHECKING:
    from eventsourcing.domain import DomainEventProtocol, TAggregateID
    from eventsourcing.persistence import Tracking


class TestProjectionRunner(TestCase):
    def test_runner(self) -> None:
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
            env={},
        )

        self.assertFalse(runner.is_interrupted.is_set())

        aggregate = Aggregate()
        aggregate.trigger_event(event_class=Aggregate.Event)
        aggregate.trigger_event(event_class=Aggregate.Event)
        recordings = runner.app.save(aggregate)

        runner.wait(recordings[-1].notification.id)
        self.assertEqual(runner.projection.view.get_created_event_counter(), 1)
        self.assertEqual(runner.projection.view.get_subsequent_event_counter(), 2)

        aggregate = Aggregate()
        aggregate.trigger_event(event_class=Aggregate.Event)
        aggregate.trigger_event(event_class=Aggregate.Event)
        recordings = runner.app.save(aggregate)

        runner.wait(recordings[-1].notification.id)
        self.assertEqual(runner.projection.view.get_created_event_counter(), 2)
        self.assertEqual(runner.projection.view.get_subsequent_event_counter(), 4)

        runner.run_forever(timeout=0.1)

        with self.assertRaises(TimeoutError):
            runner.wait(
                notification_id=(runner.app.recorder.max_notification_id() or 0) + 1,
                timeout=0.1,
            )

        aggregate.trigger_event(event_class=SpannerThrown)
        runner.app.save(aggregate)

        with self.assertRaises(SpannerThrownError):
            runner.run_forever()

        runner = ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
            env={},
        )
        aggregate = Aggregate()
        aggregate.trigger_event(event_class=SpannerThrown)
        runner.app.save(aggregate)

        with self.assertRaises(SpannerThrownError):
            runner.wait(runner.app.recorder.max_notification_id())

        self.assertTrue(runner.is_interrupted.is_set())

    def test_runner_with_topics(self) -> None:
        class AggregateEventCountersProjectionWithTopics(
            AggregateEventCountersProjection
        ):
            topics = (get_topic(Aggregate.Event),)

        runner = ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjectionWithTopics,
            view_class=POPOEventCounters,
        )

        app = runner.app
        aggregate = Aggregate()
        aggregate.trigger_event(event_class=Aggregate.Event)
        aggregate.trigger_event(event_class=Aggregate.Event)
        recordings = app.save(aggregate)

        runner.wait(recordings[-1].notification.id)
        # Should be zero because we didn't include Aggregate.Created topic.
        self.assertEqual(runner.projection.view.get_created_event_counter(), 0)
        # Should be two because we did include Aggregate.Event topic.
        self.assertEqual(runner.projection.view.get_subsequent_event_counter(), 2)

    def test_runner_stop(self) -> None:
        # Call stop() before run_forever().
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
        )
        runner.stop()
        runner.run_forever()

        # Call stop() before wait().
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
        )
        runner.stop()
        runner.wait(10000)

        exception_raised = Event()
        thread_started = Event()
        errors: list[Exception] = []

        def call_runforever(r: ProjectionRunner[Application[Any]]) -> None:
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

        def call_wait(r: ProjectionRunner[Application[Any]]) -> None:
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
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
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
        ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
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
        with ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
        ) as runner:
            self.assertIsInstance(runner, ProjectionRunner)

    def test_exit_stops_runner(self) -> None:
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=AggregateEventCountersProjection,
            view_class=POPOEventCounters,
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
            ProjectionRunner(
                application_class=Application,
                projection_class=AggregateEventCountersProjection,
                view_class=POPOEventCounters,
            ),
        ):
            raise TestError

    def test_exit_raises_processing_error(self) -> None:
        with (
            self.assertRaises(BrokenProjectionError),
            ProjectionRunner(
                application_class=Application,
                projection_class=BrokenProjection,
                view_class=POPOEventCounters,
            ) as runner,
        ):
            # Write an event.
            runner.app.save(Aggregate())
            runner.is_interrupted.wait()

    def test_warning_error_not_assigned_to_deleted_runner(self) -> None:

        # Construct a runner.
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=BrokenProjection,
            view_class=POPOEventCounters,
        )

        # Write an event.
        runner.app.save(Aggregate())

        # Error should be assigned to the runner.
        with self.assertRaises(BrokenProjectionError):
            runner.run_forever()

        # Write another event.
        runner.app.save(Aggregate())

        # Get another application sequence
        subscription = ApplicationSubscription(runner.app)

        # Get a reference to the projection.
        projection = runner.projection

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
            ProjectionRunner._process_events_loop(
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
                "ProjectionRunner was deleted before error could be assigned:",
                str(last_message),
            )

        # Check the event was set anyway.
        self.assertTrue(has_error.is_set())

    def test_wait_raises_wait_interrupted_error(self) -> None:
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=VerySlowProjection,
            view_class=POPOEventCounters,
        )
        runner.app.save(Aggregate())
        with self.assertRaises(WaitInterruptedError):
            sleep(0.5)
            runner.is_interrupted.set()
            runner.wait(1000, timeout=10)

        runner = ProjectionRunner(
            application_class=Application,
            projection_class=VerySlowProjection,
            view_class=POPOEventCounters,
        )
        runner.app.save(Aggregate())
        with self.assertRaises(WaitInterruptedError), runner:
            sleep(0.5)
            runner.is_interrupted.set()
            runner.wait(1000, timeout=10)

    def test_wait_raises_timeout_error(self) -> None:
        runner = ProjectionRunner(
            application_class=Application,
            projection_class=VerySlowProjection,
            view_class=POPOEventCounters,
        )
        runner.app.save(Aggregate())
        with self.assertRaises(TimeoutError):
            sleep(0.5)
            runner.wait(1000, timeout=0.1)

        runner = ProjectionRunner(
            application_class=Application,
            projection_class=VerySlowProjection,
            view_class=POPOEventCounters,
        )
        runner.app.save(Aggregate())
        with self.assertRaises(TimeoutError), runner:
            sleep(0.5)
            runner.wait(1000, timeout=0.1)


class BrokenProjectionError(Exception):
    pass


# Define a projection that raises an exception.
class BrokenProjection(Projection):
    @singledispatchmethod
    def process_event(
        self, domain_event: DomainEventProtocol[TAggregateID], tracking: Tracking
    ) -> None:
        raise BrokenProjectionError


# Define a projection that stalls.
class VerySlowProjection(Projection):
    @singledispatchmethod
    def process_event(
        self, domain_event: DomainEventProtocol[TAggregateID], tracking: Tracking
    ) -> None:
        sleep(2)
