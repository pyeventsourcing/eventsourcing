from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar
from unittest import TestCase
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import (
    AggregateNotFoundError,
    Application,
    ProcessingEvent,
)
from eventsourcing.dcb.application import DCBApplication
from eventsourcing.dcb.domain import EnduringObject, Tagged
from eventsourcing.dcb.msgpack import Decision, InitialDecision
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import Aggregate, DomainEventProtocol, event
from eventsourcing.persistence import (
    IntegrityError,
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


class Counter(Aggregate):
    def __init__(self, name: str) -> None:
        self.name = name
        self.count = 0

    @classmethod
    def create_id(cls, name: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"/counters/{name}")

    @event("Incremented")
    def increment(self) -> None:
        self.count += 1


class EventCountersInterface(TrackingRecorder):
    @abstractmethod
    def get_created_event_counter(self) -> int:
        pass

    @abstractmethod
    def get_subsequent_event_counter(self) -> int:
        pass

    @abstractmethod
    def incr_created_event_counter(self, tracking: Tracking) -> None:
        pass

    @abstractmethod
    def incr_subsequent_event_counter(self, tracking: Tracking) -> None:
        pass


class Counters(EventSourcedProjection[UUID]):
    @singledispatchmethod
    def policy(
        self,
        domain_event: DomainEventProtocol[UUID],
        processing_event: ProcessingEvent[UUID],
    ) -> None:
        topic = get_topic(type(domain_event))
        try:
            counter_id = Counter.create_id(topic)
            counter: Counter = self.repository.get(counter_id)
        except AggregateNotFoundError:
            counter = Counter(topic)
        counter.increment()
        processing_event.collect_events(counter)

    def get_count(self, domain_event_class: type[DomainEventProtocol[UUID]]) -> int:
        topic = get_topic(domain_event_class)
        counter_id = Counter.create_id(topic)
        try:
            counter: Counter = self.repository.get(counter_id)
        except AggregateNotFoundError:
            return 0
        return counter.count


class EventCountersViewTestCase(TestCase):
    def construct_event_counters_view(self) -> EventCountersInterface:
        raise NotImplementedError

    def test(self) -> None:
        # Construct materialised view object.
        view = self.construct_event_counters_view()

        # Check the view object is a tracking recorder.
        self.assertIsInstance(view, TrackingRecorder)

        # Check the view has processed no events.
        self.assertIsNone(view.max_tracking_id("upstream"))

        # Check the event counters are zero.
        self.assertEqual(view.get_created_event_counter(), 0)
        self.assertEqual(view.get_subsequent_event_counter(), 0)

        # Increment the "created" event counter.
        view.incr_created_event_counter(Tracking("upstream", 1))

        # Check the counted number of events.
        self.assertEqual(view.get_created_event_counter(), 1)
        self.assertEqual(view.get_subsequent_event_counter(), 0)

        # Increment the subsequent event counter.
        view.incr_subsequent_event_counter(Tracking("upstream", 2))

        # Check the counted number of events.
        self.assertEqual(view.get_created_event_counter(), 1)
        self.assertEqual(view.get_subsequent_event_counter(), 1)

        # Increment the subsequent event counter again.
        view.incr_subsequent_event_counter(Tracking("upstream", 3))

        # Check the counted number of events.
        self.assertEqual(view.get_created_event_counter(), 1)
        self.assertEqual(view.get_subsequent_event_counter(), 2)

        # Check the tracking objects have been recorded.
        self.assertEqual(view.max_tracking_id("upstream"), 3)

        # Check the tracking objects are recorded uniquely and atomically.
        with self.assertRaises(IntegrityError):
            view.incr_created_event_counter(Tracking("upstream", 3))

        # Check the counted number of events.
        self.assertEqual(view.get_created_event_counter(), 1)

        with self.assertRaises(IntegrityError):
            view.incr_subsequent_event_counter(Tracking("upstream", 3))

        # Check the counted number of events.
        self.assertEqual(view.get_subsequent_event_counter(), 2)

        # Check the wait() method returns normally when
        # we wait for a position that has been recorded.
        view.wait("upstream", 3)

        # Check the wait() method raises a TimeoutError when
        # we wait for a postion that has not been recorded.
        with self.assertRaises(TimeoutError):
            view.wait("upstream", 4, timeout=0.5)


class SpannerThrown(Aggregate.Event):
    pass


class SpannerThrownError(Exception):
    pass


class DCBSpannerThrown(Decision):
    # Avoid segmentation violation with Python 3.13
    # and MsgStruct instances with zero attributes.
    a: str


# Define a perspective.
class Thing(EnduringObject[Decision, str]):
    class Created(InitialDecision):
        thing_id: str


class TaggedDecisionCountersProjection(Projection[EventCountersInterface]):
    name = "eventcounters"
    topics: tuple[str, ...] = (
        get_topic(Thing.Created),
        get_topic(Decision),
        get_topic(DCBSpannerThrown),
    )

    @singledispatchmethod
    def process_event(self, tagged: Tagged[Decision], tracking: Tracking) -> None:
        self.process_decision(tagged.decision, tracking)

    @singledispatchmethod
    def process_decision(self, _: Decision, tracking: Tracking) -> None:
        self.view.insert_tracking(tracking)

    @process_decision.register
    def _(self, _: InitialDecision, tracking: Tracking) -> None:
        self.view.incr_created_event_counter(tracking)

    @process_decision.register
    def _(self, _: Decision, tracking: Tracking) -> None:
        self.view.incr_subsequent_event_counter(tracking)

    @process_decision.register
    def _(self, _: DCBSpannerThrown, __: Tracking) -> None:
        msg = "This is a deliberate bug"
        raise SpannerThrownError(msg)


class AggregateEventCountersProjection(Projection[EventCountersInterface]):
    name = "eventcounters"
    topics: tuple[str, ...] = (
        get_topic(Aggregate.Created),
        get_topic(Aggregate.Event),
        get_topic(SpannerThrown),
    )

    @singledispatchmethod
    def process_event(self, _: Aggregate.Event, tracking: Tracking) -> None:
        self.view.insert_tracking(tracking)

    @process_event.register
    def aggregate_created(self, _: Aggregate.Created, tracking: Tracking) -> None:
        self.view.incr_created_event_counter(tracking)

    @process_event.register
    def aggregate_event(self, _: Aggregate.Event, tracking: Tracking) -> None:
        self.view.incr_subsequent_event_counter(tracking)

    @process_event.register
    def spanner_thrown(self, _: SpannerThrown, __: Tracking) -> None:
        msg = "This is a deliberate bug"
        raise SpannerThrownError(msg)


class AggregateEventCountersProjectionTestCase(TestCase, ABC):
    view_class: type[EventCountersInterface]
    env: ClassVar[dict[str, str]] = {}

    def test_event_counters_projection(self) -> None:
        # Construct runner with application, projection, and recorder.
        runner = ProjectionRunner(
            application_class=Application[UUID],
            projection_class=AggregateEventCountersProjection,
            view_class=self.view_class,
            env=self.env,
        )
        with runner:

            # Get "read" and "write" model instances from the runner.
            write_model = runner.app
            read_model = runner.projection.view

            # Write some events.
            aggregate = Aggregate()
            aggregate.trigger_event(event_class=Aggregate.Event)
            aggregate.trigger_event(event_class=Aggregate.Event)
            recordings = write_model.save(aggregate)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=recordings[-1].notification.id,
            )

            # Query the read model.
            self.assertEqual(read_model.get_created_event_counter(), 1)
            self.assertEqual(read_model.get_subsequent_event_counter(), 2)

            # Write some more events.
            aggregate = Aggregate()
            aggregate.trigger_event(event_class=Aggregate.Event)
            aggregate.trigger_event(event_class=Aggregate.Event)
            recordings = write_model.save(aggregate)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=recordings[-1].notification.id,
            )

            # Query the read model.
            self.assertEqual(read_model.get_created_event_counter(), 2)
            self.assertEqual(read_model.get_subsequent_event_counter(), 4)

    def test_run_forever_raises_projection_error(self) -> None:
        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=Application[UUID],
            projection_class=AggregateEventCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:
            write_model = runner.app
            read_model = runner.projection.view

            # Write some events.
            aggregate = Aggregate()
            aggregate.trigger_event(event_class=SpannerThrown)
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


class TaggedDecisionCountersProjectionTestCase(TestCase, ABC):
    view_class: type[EventCountersInterface]
    env: ClassVar[dict[str, str]]

    def test_event_counters_projection(self) -> None:

        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=DCBApplication,
            projection_class=TaggedDecisionCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:

            # Get "read" and "write" model instances from the runner.
            write_model = runner.app
            read_model = runner.projection.view

            # Write some events.
            perspective = Thing()
            perspective.trigger_event(Decision)
            perspective.trigger_event(Decision)
            self.assertEqual(3, len(perspective.new_decisions))
            position = write_model.repository.save(perspective)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=position,
            )

            # Query the read model.
            self.assertEqual(read_model.get_created_event_counter(), 1)
            self.assertEqual(read_model.get_subsequent_event_counter(), 2)

            # Write some more events.
            perspective = Thing()
            perspective.trigger_event(Decision)
            perspective.trigger_event(Decision)
            position = write_model.repository.save(perspective)

            # Wait for the events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=position,
            )

            # Query the read model.
            self.assertEqual(read_model.get_created_event_counter(), 2)
            self.assertEqual(read_model.get_subsequent_event_counter(), 4)

    def test_run_forever_raises_projection_error(self) -> None:
        # Construct runner with application, projection, and recorder.
        with ProjectionRunner(
            application_class=DCBApplication,
            projection_class=TaggedDecisionCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:
            write_model = runner.app
            read_model = runner.projection.view

            # Write some events.
            perspective = Thing()
            perspective.trigger_event(DCBSpannerThrown, a="")
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
            application_class=Application, projection_class=Counters, env=self.env
        ) as runner:
            recordings = runner.app.save(Aggregate())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(1, runner.projection.get_count(Aggregate.Created))
            self.assertEqual(0, runner.projection.get_count(Aggregate.Event))

            recordings = runner.app.save(Aggregate())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(2, runner.projection.get_count(Aggregate.Created))
            self.assertEqual(0, runner.projection.get_count(Aggregate.Event))

            recordings = runner.app.save(Aggregate())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(3, runner.projection.get_count(Aggregate.Created))
            self.assertEqual(0, runner.projection.get_count(Aggregate.Event))

            aggregate = Aggregate()
            aggregate.trigger_event(Aggregate.Event)
            recordings = runner.app.save(aggregate)
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(4, runner.projection.get_count(Aggregate.Created))
            self.assertEqual(1, runner.projection.get_count(Aggregate.Event))
