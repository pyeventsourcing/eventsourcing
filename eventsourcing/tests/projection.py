from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, override
from unittest import TestCase
from uuid import NAMESPACE_URL, uuid4, uuid5

from eventsourcing.application import (
    AggregateNotFoundError,
    ProcessingEvent,
)
from eventsourcing.decorator import triggers
from eventsourcing.domain import EventEnvelope
from eventsourcing.metadata import put_metadata_in_context
from eventsourcing.msgspec import (
    Aggregate,
    AggregatesApplication,
    DcbApplication,
    Decision,
    EnduringObject,
    EventSourcedProjection,
)
from eventsourcing.persistence import (
    IntegrityError,
    Tracking,
    TrackingRecorder,
)
from eventsourcing.projection import (
    EventProcessor,
    EventSourcedProjectionRunner,
    ProjectionRunner,
)
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from eventsourcing.types import AggregateEventProtocol


class StudentAnalyticsView(TrackingRecorder):
    @abstractmethod
    def get_student_registered_counter(self) -> int:
        pass

    @abstractmethod
    def get_student_name_changed_counter(self) -> int:
        pass

    @abstractmethod
    def incr_student_registered_counter(self, tracking: Tracking) -> None:
        pass

    @abstractmethod
    def incr_student_name_changed_counter(self, tracking: Tracking) -> None:
        pass


class StudentAnalyticsViewTestCase(TestCase):
    def construct_event_counters_view(self) -> StudentAnalyticsView:
        raise NotImplementedError

    def test(self) -> None:
        # Construct materialised view object.
        view = self.construct_event_counters_view()

        # Check the view object is a tracking recorder.
        self.assertIsInstance(view, TrackingRecorder)

        # Check the view has processed no events.
        self.assertIsNone(view.max_tracking_id("upstream"))

        # Check the event counters are zero.
        self.assertEqual(view.get_student_registered_counter(), 0)
        self.assertEqual(view.get_student_name_changed_counter(), 0)

        # Increment the "created" event counter.
        view.incr_student_registered_counter(Tracking("upstream", 1))

        # Check the counted number of events.
        self.assertEqual(view.get_student_registered_counter(), 1)
        self.assertEqual(view.get_student_name_changed_counter(), 0)

        # Increment the subsequent event counter.
        view.incr_student_name_changed_counter(Tracking("upstream", 2))

        # Check the counted number of events.
        self.assertEqual(view.get_student_registered_counter(), 1)
        self.assertEqual(view.get_student_name_changed_counter(), 1)

        # Increment the subsequent event counter again.
        view.incr_student_name_changed_counter(Tracking("upstream", 3))

        # Check the counted number of events.
        self.assertEqual(view.get_student_registered_counter(), 1)
        self.assertEqual(view.get_student_name_changed_counter(), 2)

        # Check the tracking objects have been recorded.
        self.assertEqual(view.max_tracking_id("upstream"), 3)

        # Check the tracking objects are recorded uniquely and atomically.
        with self.assertRaises(IntegrityError):
            view.incr_student_registered_counter(Tracking("upstream", 3))

        # Check the counted number of events.
        self.assertEqual(view.get_student_registered_counter(), 1)

        with self.assertRaises(IntegrityError):
            view.incr_student_name_changed_counter(Tracking("upstream", 3))

        # Check the counted number of events.
        self.assertEqual(view.get_student_name_changed_counter(), 2)

        # Check the wait() method returns normally when
        # we wait for a position that has been recorded.
        view.wait("upstream", 3)

        # Check the wait() method raises a TimeoutError when
        # we wait for a postion that has not been recorded.
        with self.assertRaises(TimeoutError):
            view.wait("upstream", 4, timeout=0.5)


class SpannerThrownError(Exception):
    pass


class SpannerThrown(Decision):
    student_id: str
    # # Avoid segmentation violation with Python 3.13
    # # and MsgStruct instances with zero attributes.
    # thing_id: str
    # a: str


class StudentRegistered(Decision):
    student_id: str


class StudentNameChanged(Decision):
    student_id: str


class StudentAggregate(Aggregate):
    @triggers(StudentRegistered)
    def __init__(self, student_id: str) -> None:
        pass

    @staticmethod
    def create_id(student_id: str) -> str:
        return student_id

    @triggers(StudentNameChanged)
    def change_name(self) -> None:
        pass

    @override
    def trigger_event[**P](
        self,
        decision_cls: Callable[P, Decision],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        if "student_id" not in kwargs:
            kwargs["student_id"] = self.id
        super().trigger_event(decision_cls, *args, **kwargs)


# Define a perspective.
class StudentEntity(EnduringObject):
    continuity_id_name = "student_id"

    @triggers(StudentRegistered)
    def __init__(self) -> None:
        pass

    @triggers(StudentNameChanged)
    def change_name(self) -> None:
        pass


class StudentAnalyticsEventProcessor(
    EventProcessor[EventEnvelope[Decision], StudentAnalyticsView]
):
    context_name = "eventcounters"
    topics: Sequence[str] = (
        get_topic(StudentRegistered),
        get_topic(StudentNameChanged),
        get_topic(SpannerThrown),
    )

    @override
    def process_event(
        self, envelope: EventEnvelope[Decision], tracking: Tracking
    ) -> None:
        match envelope.decision:
            case StudentRegistered():
                self.view.incr_student_registered_counter(tracking)
            case StudentNameChanged():
                self.view.incr_student_name_changed_counter(tracking)
            case SpannerThrown():
                msg = "This is a deliberate bug"
                raise SpannerThrownError(msg)
            case _:
                self.view.insert_tracking(tracking)


class AggregateEventProjectionTestCase[TTrackingRecorder: StudentAnalyticsView](
    TestCase, ABC
):
    view_class: type[TTrackingRecorder]
    env: ClassVar[dict[str, str]] = {}

    def test_event_counters_projection(self) -> None:
        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=AggregatesApplication,
            projection_class=StudentAnalyticsEventProcessor,
            view_class=self.view_class,
            env=self.env,
        ) as runner:

            # Get "read" and "write" model instances from the runner.
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            aggregate = StudentAggregate(student_id=str(uuid4()))
            aggregate.change_name()
            aggregate.change_name()
            recordings = write_model.save(aggregate)

            # Wait for the events to be processed.
            read_model.wait(
                context_name=write_model.context_name,
                notification_id=recordings[-1].notification.id,
                timeout=100,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 1)
            self.assertEqual(read_model.get_student_name_changed_counter(), 2)

            # Write some more events.
            aggregate = StudentAggregate(student_id=str(uuid4()))
            aggregate.change_name()
            aggregate.change_name()
            recordings = write_model.save(aggregate)

            # Wait for the events to be processed.
            read_model.wait(
                context_name=write_model.context_name,
                notification_id=recordings[-1].notification.id,
                timeout=100,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 2)
            self.assertEqual(read_model.get_student_name_changed_counter(), 4)

    def test_run_forever_raises_projection_error(self) -> None:
        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=AggregatesApplication,
            projection_class=StudentAnalyticsEventProcessor,
            view_class=self.view_class,
            env=self.env,
        ) as runner:
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            aggregate = StudentAggregate(student_id=str(uuid4()))
            aggregate.trigger_event(SpannerThrown, student_id=aggregate.id)
            recordings = write_model.save(aggregate)

            # Projection runner terminates with projection error.
            with self.assertRaises(SpannerThrownError):
                runner.run_forever(timeout=5)

            # Wait times out (event has not been processed).
            with self.assertRaises(TimeoutError):
                read_model.wait(
                    context_name=write_model.context_name,
                    notification_id=recordings[-1].notification.id,
                )


class TaggedEventProjectionTestCase(TestCase, ABC):
    view_class: type[StudentAnalyticsView]
    env: ClassVar[dict[str, str]]

    def test_event_counters_projection(self) -> None:

        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=DcbApplication,
            projection_class=StudentAnalyticsEventProcessor,
            view_class=self.view_class,
            env=self.env,
        ) as runner:

            # Get "read" and "write" model instances from the runner.
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            student = StudentEntity()
            student.change_name()
            student.change_name()
            self.assertEqual(3, len(student.new_decisions))
            position = write_model.repository.save(student)

            # Wait for the events to be processed.
            read_model.wait(
                context_name=write_model.context_name,
                notification_id=position,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 1)
            self.assertEqual(read_model.get_student_name_changed_counter(), 2)

            # Write some more events.
            student = StudentEntity()
            student.change_name()
            student.change_name()
            position = write_model.repository.save(student)

            # Wait for the events to be processed.
            read_model.wait(
                context_name=write_model.context_name,
                notification_id=position,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 2)
            self.assertEqual(read_model.get_student_name_changed_counter(), 4)

    def test_run_forever_raises_projection_error(self) -> None:
        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=DcbApplication,
            projection_class=StudentAnalyticsEventProcessor,
            view_class=self.view_class,
            env=self.env,
        ) as runner:
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            student = StudentEntity()
            student.change_name()
            student.trigger_event(SpannerThrown, student_id=student.id)
            position = write_model.repository.save(student)

            # Projection runner terminates with projection error.
            with self.assertRaises(SpannerThrownError):
                runner.run_forever(timeout=5)

            # Wait times out (event has not been processed).
            with self.assertRaises(TimeoutError):
                read_model.wait(
                    context_name=write_model.context_name,
                    notification_id=position,
                )


class CounterAggregate(Aggregate):
    class Created(Decision):
        name: str

    class Incremented(Decision):
        pass

    @triggers(Created)
    def __init__(self, name: str) -> None:
        self.name = name
        self.count = 0

    @staticmethod
    def create_id(name: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"/counters/{name}"))

    @triggers(Incremented)
    def increment(self) -> None:
        self.count += 1


class CounterAggregatesApplication(EventSourcedProjection):
    @override
    def policy(
        self,
        envelope: AggregateEventProtocol[Decision],
        processing_event: ProcessingEvent[Decision],
    ) -> None:
        topic = get_topic(type(envelope.decision))
        try:
            counter_id = CounterAggregate.create_id(topic)
            counter = self.repository.get(counter_id, CounterAggregate)
        except AggregateNotFoundError:
            counter = CounterAggregate(name=topic)
        counter.increment()
        processing_event.collect_events(counter)

    def get_count(self, domain_event_class: type[Any]) -> int:
        topic = get_topic(domain_event_class)
        counter_id = CounterAggregate.create_id(topic)
        try:
            counter = self.repository.get(counter_id, CounterAggregate)
        except AggregateNotFoundError:
            return 0
        return counter.count


class EventSourcedProjectionTestCase(TestCase):
    env: ClassVar[dict[str, str]] = {}

    def test_event_sourced_projection(self) -> None:
        with EventSourcedProjectionRunner(
            upstream_application_class=AggregatesApplication,
            downstream_application_class=CounterAggregatesApplication,
            env=self.env,
        ) as runner:
            app_max_id = runner.app.recorder.max_notification_id()
            projection_max_id = runner.downstream.recorder.max_notification_id()

            def fresh_metadata() -> dict[str, str]:
                correlation_id = uuid4()
                return {
                    "correlation_id": str(correlation_id),
                    "causation_id": str(correlation_id),
                }

            with put_metadata_in_context(fresh_metadata()):
                recordings = runner.app.save(StudentAggregate(student_id=str(uuid4())))
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(1, runner.downstream.get_count(StudentRegistered))
            self.assertEqual(0, runner.downstream.get_count(StudentNameChanged))

            with put_metadata_in_context(fresh_metadata()):
                recordings = runner.app.save(StudentAggregate(student_id=str(uuid4())))
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(2, runner.downstream.get_count(StudentRegistered))
            self.assertEqual(0, runner.downstream.get_count(StudentNameChanged))

            with put_metadata_in_context(fresh_metadata()):
                recordings = runner.app.save(StudentAggregate(student_id=str(uuid4())))
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(3, runner.downstream.get_count(StudentRegistered))
            self.assertEqual(0, runner.downstream.get_count(StudentNameChanged))

            with put_metadata_in_context(fresh_metadata()):
                aggregate = StudentAggregate(student_id=str(uuid4()))
                aggregate.change_name()
            recordings = runner.app.save(aggregate)
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(4, runner.downstream.get_count(StudentRegistered))
            self.assertEqual(1, runner.downstream.get_count(StudentNameChanged))

            # Check the correlation and causation IDs.
            original_events: dict[str, AggregateEventProtocol[Decision]] = {}
            for notification in runner.app.notification_log.select(
                start=app_max_id,
                limit=10,
                inclusive_of_start=False,
            ):
                domain_event = runner.downstream.mapper.to_domain_event(notification)
                self.assertEqual(
                    domain_event.metadata["correlation_id"],
                    domain_event.metadata["causation_id"],
                )
                original_events[str(domain_event.uuid)] = domain_event

            for notification in runner.downstream.notification_log.select(
                start=projection_max_id,
                limit=10,
                inclusive_of_start=False,
            ):
                domain_event = runner.downstream.mapper.to_domain_event(notification)
                self.assertIn(domain_event.metadata["causation_id"], original_events)
                causal_event = original_events[domain_event.metadata["causation_id"]]
                self.assertEqual(
                    causal_event.metadata["correlation_id"],
                    domain_event.metadata["correlation_id"],
                )
