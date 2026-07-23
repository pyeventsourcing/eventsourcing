from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar
from unittest import TestCase
from uuid import NAMESPACE_URL, uuid4, uuid5

from typing_extensions import deprecated

from eventsourcing.application import (
    AggregateNotFoundError,
    ProcessingEvent,
)
from eventsourcing.domain import (
    AggregateEvent,
    EventEnvelope,
    TaggedEvent,
    put_metadata_in_context,
    triggers,
)
from eventsourcing.msgspec import (
    Aggregate,
    AggregatesApplication,
    DCBApplication,
    Decision,
    EnduringObject,
)
from eventsourcing.persistence import (
    IntegrityError,
    ProcessRecorder,
    Tracking,
    TrackingRecorder,
)
from eventsourcing.projection import (
    EventSourcedProjection,
    EventSourcedProjectionRunner,
    Projection,
    ProjectionRunner,
)
from eventsourcing.utils import get_topic


class Student(Aggregate):
    class Registered(Decision):
        pass

    class NameChanged(Decision):
        pass

    @triggers(Registered)
    def __init__(self) -> None:
        pass

    @triggers(NameChanged)
    def change_name(self) -> None:
        pass


class Counter(Aggregate):
    class Created(Decision):
        name: str

    class Incremented(Decision):
        pass

    @triggers(Created)
    def __init__(self, name: str) -> None:
        self.name = name
        self.count = 0

    @classmethod
    def create_id(cls, name: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"/counters/{name}"))

    @triggers(Incremented)
    def increment(self) -> None:
        self.count += 1


class EventCountersView(TrackingRecorder):
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


@deprecated("Use EventCountersView instead")
class EventCountersInterface(EventCountersView, ABC):
    pass


class Counters(
    AggregatesApplication,
    EventSourcedProjection[Decision, ProcessRecorder, EventEnvelope[Decision]],
):
    def policy(
        self,
        envelope: EventEnvelope[Decision],
        processing_event: ProcessingEvent[Decision],
    ) -> None:
        topic = get_topic(type(envelope.decision))
        try:
            counter_id = Counter.create_id(topic)
            counter = self.repository.get(counter_id, Counter)
        except AggregateNotFoundError:
            counter = Counter(name=topic)
        counter.increment()
        processing_event.collect_events(counter)

    def get_count(self, domain_event_class: type[Any]) -> int:
        topic = get_topic(domain_event_class)
        counter_id = Counter.create_id(topic)
        try:
            counter = self.repository.get(counter_id, Counter)
        except AggregateNotFoundError:
            return 0
        return counter.count


class EventCountersViewTestCase(TestCase):
    def construct_event_counters_view(self) -> EventCountersView:
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


class SpannerThrown(Decision):
    pass


class SpannerThrownError(Exception):
    pass


class DCBSpannerThrown(Decision):
    # Avoid segmentation violation with Python 3.13
    # and MsgStruct instances with zero attributes.
    thing_id: str
    a: str


# Define a perspective.
class Thing(EnduringObject):
    class Created(Decision):
        thing_id: str

    class Next(Decision):
        thing_id: str

    @triggers(Created)
    def __init__(self, thing_id: str) -> None:
        self.id = thing_id


class DecisionCountersProjection(Projection[EventCountersView, TaggedEvent[Decision]]):
    name = "eventcounters"
    topics: tuple[str, ...] = (
        get_topic(Thing.Created),
        get_topic(Thing.Next),
        get_topic(DCBSpannerThrown),
    )

    def process_event(
        self, envelope: TaggedEvent[Decision], tracking: Tracking
    ) -> None:
        match envelope.decision:
            case Thing.Created():
                self.view.incr_student_registered_counter(tracking)
            case DCBSpannerThrown():
                msg = "This is a deliberate bug"
                raise SpannerThrownError(msg)
            case Thing.Next():
                self.view.incr_student_name_changed_counter(tracking)
            case _:
                self.view.insert_tracking(tracking)


class StudentEventCountersProjection(
    Projection[EventCountersView, AggregateEvent[Decision]]
):
    name = "eventcounters"
    topics: tuple[str, ...] = (
        get_topic(Student.Registered),
        get_topic(Student.NameChanged),
        get_topic(SpannerThrown),
    )

    def process_event(
        self, envelope: AggregateEvent[Decision], tracking: Tracking
    ) -> None:
        match envelope.decision:
            case Student.Registered():
                self.view.incr_student_registered_counter(tracking)
            case Student.NameChanged():
                self.view.incr_student_name_changed_counter(tracking)
            case SpannerThrown():
                msg = "This is a deliberate bug"
                raise SpannerThrownError(msg)
            case _:
                self.view.insert_tracking(tracking)


class AggregateEventCountersProjectionTestCase(TestCase, ABC):
    view_class: type[EventCountersView]
    env: ClassVar[dict[str, str]] = {}

    def test_event_counters_projection(self) -> None:
        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=AggregatesApplication,
            projection_class=StudentEventCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:

            # Get "read" and "write" model instances from the runner.
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            aggregate = Student()
            aggregate.trigger_event(Student.NameChanged)
            aggregate.trigger_event(Student.NameChanged)
            recordings = write_model.save(aggregate)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=recordings[-1].notification.id,
                timeout=100,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 1)
            self.assertEqual(read_model.get_student_name_changed_counter(), 2)

            # Write some more events.
            aggregate = Student()
            aggregate.trigger_event(Student.NameChanged)
            aggregate.trigger_event(Student.NameChanged)
            recordings = write_model.save(aggregate)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
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
            projection_class=StudentEventCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            aggregate = Student()
            aggregate.trigger_event(SpannerThrown)
            recordings = write_model.save(aggregate)

            # Projection runner terminates with projection error.
            with self.assertRaises(SpannerThrownError):
                runner.run_forever(timeout=5)

            # Wait times out (event has not been processed).
            with self.assertRaises(TimeoutError):
                read_model.wait(
                    application_name=write_model.name,
                    notification_id=recordings[-1].notification.id,
                )


class DecisionCountersProjectionTestCase(TestCase, ABC):
    view_class: type[EventCountersView]
    env: ClassVar[dict[str, str]]

    def test_event_counters_projection(self) -> None:

        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=DCBApplication,
            projection_class=DecisionCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:

            # Get "read" and "write" model instances from the runner.
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            perspective = Thing(thing_id=str("thing-" + str(uuid4())))
            perspective.trigger_event(Thing.Next, thing_id=perspective.id)
            perspective.trigger_event(Thing.Next, thing_id=perspective.id)
            self.assertEqual(3, len(perspective.new_decisions))
            position = write_model.repository.save(perspective)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=position,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 1)
            self.assertEqual(read_model.get_student_name_changed_counter(), 2)

            # Write some more events.
            perspective = Thing(thing_id=str("thing-" + str(uuid4())))
            perspective.trigger_event(Thing.Next, thing_id=perspective.id)
            perspective.trigger_event(Thing.Next, thing_id=perspective.id)
            position = write_model.repository.save(perspective)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=position,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 2)
            self.assertEqual(read_model.get_student_name_changed_counter(), 4)

    def test_run_forever_raises_projection_error(self) -> None:
        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=DCBApplication,
            projection_class=DecisionCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:
            write_model = runner.app
            read_model = runner.view

            # Write some events.
            perspective = Thing(thing_id=str("thing-" + str(uuid4())))
            perspective.trigger_event(DCBSpannerThrown, a="", thing_id=perspective.id)
            position = write_model.repository.save(perspective)

            # Projection runner terminates with projection error.
            with self.assertRaises(SpannerThrownError):
                runner.run_forever(timeout=5)

            # Wait times out (event has not been processed).
            with self.assertRaises(TimeoutError):
                read_model.wait(
                    application_name=write_model.name,
                    notification_id=position,
                )


class EventSourcedProjectionTestCase(TestCase):
    env: ClassVar[dict[str, str]] = {}

    def test_event_sourced_projection(self) -> None:
        with EventSourcedProjectionRunner(
            application_class=AggregatesApplication,
            projection_class=Counters,
            env=self.env,
        ) as runner:
            app_max_id = runner.app.recorder.max_notification_id()
            projection_max_id = runner.projection.recorder.max_notification_id()

            def fresh_metadata() -> dict[str, str]:
                correlation_id = uuid4()
                return {
                    "correlation_id": str(correlation_id),
                    "causation_id": str(correlation_id),
                }

            with put_metadata_in_context(fresh_metadata()):
                recordings = runner.app.save(Student())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(1, runner.projection.get_count(Student.Registered))
            self.assertEqual(0, runner.projection.get_count(Student.NameChanged))

            with put_metadata_in_context(fresh_metadata()):
                recordings = runner.app.save(Student())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(2, runner.projection.get_count(Student.Registered))
            self.assertEqual(0, runner.projection.get_count(Student.NameChanged))

            with put_metadata_in_context(fresh_metadata()):
                recordings = runner.app.save(Student())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(3, runner.projection.get_count(Student.Registered))
            self.assertEqual(0, runner.projection.get_count(Student.NameChanged))

            with put_metadata_in_context(fresh_metadata()):
                aggregate = Student()
                aggregate.trigger_event(Student.NameChanged)
            recordings = runner.app.save(aggregate)
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(4, runner.projection.get_count(Student.Registered))
            self.assertEqual(1, runner.projection.get_count(Student.NameChanged))

            # Check the correlation and causation IDs.
            original_events: dict[str, AggregateEvent[Decision]] = {}
            for notification in runner.app.notification_log.select(
                start=app_max_id,
                limit=10,
                inclusive_of_start=False,
            ):
                domain_event = runner.projection.mapper.to_domain_event(notification)
                self.assertEqual(
                    domain_event.metadata["correlation_id"],
                    domain_event.metadata["causation_id"],
                )
                original_events[str(domain_event.uuid)] = domain_event

            for notification in runner.projection.notification_log.select(
                start=projection_max_id,
                limit=10,
                inclusive_of_start=False,
            ):
                domain_event = runner.projection.mapper.to_domain_event(notification)
                self.assertIn(domain_event.metadata["causation_id"], original_events)
                causal_event = original_events[domain_event.metadata["causation_id"]]
                self.assertEqual(
                    causal_event.metadata["correlation_id"],
                    domain_event.metadata["correlation_id"],
                )
