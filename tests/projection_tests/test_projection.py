from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, cast
from unittest import TestCase, skipIf
from uuid import UUID

from psycopg.sql import SQL, Identifier

from eventsourcing.application import Application
from eventsourcing.dcb.application import DCBApplication
from eventsourcing.dcb.domain import Perspective, Selector, Tagged
from eventsourcing.dcb.msgpack import Decision, InitialDecision, MessagePackMapper
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import (
    InfrastructureFactory,
    IntegrityError,
    Tracking,
    TrackingRecorder,
)
from eventsourcing.popo import POPOTrackingRecorder
from eventsourcing.postgres import (
    PostgresDatastore,
    PostgresFactory,
    PostgresTrackingRecorder,
)
from eventsourcing.projection import Projection, ProjectionRunner
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import Environment, get_topic

if TYPE_CHECKING:
    from collections.abc import Sequence


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


class POPOEventCounters(POPOTrackingRecorder, EventCountersInterface):
    def __init__(self) -> None:
        super().__init__()
        self._created_event_counter = 0
        self._subsequent_event_counter = 0

    def get_created_event_counter(self) -> int:
        return self._created_event_counter

    def get_subsequent_event_counter(self) -> int:
        return self._subsequent_event_counter

    def incr_created_event_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._assert_tracking_uniqueness(tracking)
            self._insert_tracking(tracking)
            self._created_event_counter += 1

    def incr_subsequent_event_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._assert_tracking_uniqueness(tracking)
            self._insert_tracking(tracking)
            self._subsequent_event_counter += 1


class TestPOPOEventCounters(EventCountersViewTestCase):
    def construct_event_counters_view(self) -> EventCountersInterface:
        return POPOEventCounters()


class TestPostgresEventCounters(EventCountersViewTestCase):
    def setUp(self) -> None:
        self.factory = cast(
            PostgresFactory,
            InfrastructureFactory.construct(
                env=Environment(
                    name="eventcounters",
                    env={
                        "PERSISTENCE_MODULE": "eventsourcing.postgres",
                        "POSTGRES_DBNAME": "eventsourcing",
                        "POSTGRES_HOST": "127.0.0.1",
                        "POSTGRES_PORT": "5432",
                        "POSTGRES_USER": "eventsourcing",
                        "POSTGRES_PASSWORD": "eventsourcing",
                    },
                )
            ),
        )

    def construct_event_counters_view(self) -> EventCountersInterface:
        return self.factory.tracking_recorder(PostgresEventCounters)

    def tearDown(self) -> None:
        self.factory.close()
        drop_tables()


class PostgresEventCounters(PostgresTrackingRecorder, EventCountersInterface):
    _created_event_counter_name = "CREATED_EVENTS"
    _subsequent_event_counter_name = "SUBSEQUENT_EVENTS"

    def __init__(
        self,
        datastore: PostgresDatastore,
        **kwargs: Any,
    ):
        super().__init__(datastore, **kwargs)
        assert self.tracking_table_name.endswith("_tracking")  # Because we replace it.
        self.counters_table_name = self.tracking_table_name.replace("_tracking", "")
        self.check_identifier_length(self.counters_table_name)
        self.sql_create_statements.append(
            SQL(
                "CREATE TABLE IF NOT EXISTS {0}.{1} ("
                "counter_name text, "
                "counter bigint, "
                "PRIMARY KEY "
                "(counter_name))"
            ).format(
                Identifier(self.datastore.schema),
                Identifier(self.counters_table_name),
            )
        )

        self.select_counter_statement = SQL(
            "SELECT counter FROM {0}.{1} WHERE counter_name=%s"
        ).format(
            Identifier(self.datastore.schema),
            Identifier(self.counters_table_name),
        )

        self.incr_counter_statement = SQL(
            "INSERT INTO {0}.{1} VALUES (%s, 1) "
            "ON CONFLICT (counter_name) DO UPDATE "
            "SET counter = {0}.{1}.counter + 1"
        ).format(
            Identifier(self.datastore.schema),
            Identifier(self.counters_table_name),
        )

    def get_created_event_counter(self) -> int:
        return self._select_counter(self._created_event_counter_name)

    def get_subsequent_event_counter(self) -> int:
        return self._select_counter(self._subsequent_event_counter_name)

    def incr_created_event_counter(self, tracking: Tracking) -> None:
        self._incr_counter(self._created_event_counter_name, tracking)

    def incr_subsequent_event_counter(self, tracking: Tracking) -> None:
        self._incr_counter(self._subsequent_event_counter_name, tracking)

    def _select_counter(self, name: str) -> int:
        with self.datastore.transaction(commit=False) as curs:
            curs.execute(
                query=self.select_counter_statement,
                params=(name,),
                prepare=True,
            )
            fetchone = curs.fetchone()
            return fetchone["counter"] if fetchone else 0

    def _incr_counter(self, name: str, tracking: Tracking) -> None:
        with self.datastore.transaction(commit=True) as curs:
            self._insert_tracking(curs, tracking)
            curs.execute(
                query=self.incr_counter_statement,
                params=(name,),
                prepare=True,
            )


class SpannerThrown(Aggregate.Event):
    pass


class DCBSpannerThrown(Decision):
    # Avoid segmentation violation with Python 3.13
    # and MsgStruct instances with zero attributes.
    a: str


class SpannerThrownError(Exception):
    pass


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


class TaggedDecisionCountersProjection(Projection[EventCountersInterface]):
    name = "eventcounters"
    topics: tuple[str, ...] = (
        get_topic(InitialDecision),
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


class TestAggregateEventCountersProjection(TestCase, ABC):
    view_class: type[EventCountersInterface] = POPOEventCounters
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


class MyPerspective(Perspective[Decision]):
    @property
    def cb(self) -> Selector | Sequence[Selector]:
        return []


# TODO: Figure out actually what is causing segmentation violations with Python3.13.
#  - is happening in this test when whole test suite is run, but not when run alone
#  - was happening when run alone when DCBSpannerThrown has no attributes
#  - maybe something to do with deepcopy() in InMemoryRecorder?
@skipIf(sys.version_info[0:2] == (3, 13), "Weird occasional segmentation violation")
class TestTaggedDecisionCountersProjection(TestCase, ABC):
    view_class: type[EventCountersInterface] = POPOEventCounters
    env: ClassVar[dict[str, str]] = {"MAPPER_TOPIC": get_topic(MessagePackMapper)}

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
            perspective = MyPerspective()
            perspective.append_new_decision(
                Tagged([], InitialDecision(originator_topic=""))
            )
            perspective.append_new_decision(Tagged([], Decision()))
            perspective.append_new_decision(Tagged([], Decision()))
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
            perspective = MyPerspective()
            perspective.append_new_decision(
                Tagged([], InitialDecision(originator_topic=""))
            )
            perspective.append_new_decision(Tagged([], Decision()))
            perspective.append_new_decision(Tagged([], Decision()))
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
            perspective = MyPerspective()
            perspective.append_new_decision(Tagged([], DCBSpannerThrown(a="")))
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


class TestAggregateEventCountersProjectionWithPostgres(
    TestAggregateEventCountersProjection
):
    view_class = PostgresEventCounters
    env: ClassVar[dict[str, str]] = {
        "APPLICATION_PERSISTENCE_MODULE": "eventsourcing.postgres",
        "APPLICATION_POSTGRES_DBNAME": "eventsourcing",
        "APPLICATION_POSTGRES_HOST": "127.0.0.1",
        "APPLICATION_POSTGRES_PORT": "5432",
        "APPLICATION_POSTGRES_USER": "eventsourcing",
        "APPLICATION_POSTGRES_PASSWORD": "eventsourcing",
        "EVENTCOUNTERS_PERSISTENCE_MODULE": "eventsourcing.postgres",
        "EVENTCOUNTERS_POSTGRES_DBNAME": "eventsourcing",
        "EVENTCOUNTERS_POSTGRES_HOST": "127.0.0.1",
        "EVENTCOUNTERS_POSTGRES_PORT": "5432",
        "EVENTCOUNTERS_POSTGRES_USER": "eventsourcing",
        "EVENTCOUNTERS_POSTGRES_PASSWORD": "eventsourcing",
    }

    def test_event_counters_projection(self) -> None:
        super().test_event_counters_projection()

        # Resume....
        with ProjectionRunner(
            application_class=Application[UUID],
            projection_class=AggregateEventCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ):

            # Construct separate instance of "write model".
            write_model = Application[UUID](self.env)

            # Construct separate instance of "read model".
            read_model = (
                InfrastructureFactory[EventCountersInterface]
                .construct(
                    env=Environment(
                        name=AggregateEventCountersProjection.name, env=self.env
                    )
                )
                .tracking_recorder(self.view_class)
            )

            # Write some events.
            aggregate = Aggregate()
            aggregate.trigger_event(event_class=Aggregate.Event)
            aggregate.trigger_event(event_class=Aggregate.Event)
            recordings = write_model.save(aggregate)

            # Wait for events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=recordings[-1].notification.id,
            )

            # Query the read model.
            self.assertEqual(read_model.get_created_event_counter(), 3)
            self.assertEqual(read_model.get_subsequent_event_counter(), 6)

            # Write some more events.
            aggregate = Aggregate()
            aggregate.trigger_event(event_class=Aggregate.Event)
            aggregate.trigger_event(event_class=Aggregate.Event)
            recordings = write_model.save(aggregate)

            # Wait for events to be processed.
            read_model.wait(
                application_name=write_model.name,
                notification_id=recordings[-1].notification.id,
            )

            # Query the read model.
            self.assertEqual(read_model.get_created_event_counter(), 4)
            self.assertEqual(read_model.get_subsequent_event_counter(), 8)

    def test_run_forever_raises_projection_error(self) -> None:
        super().test_run_forever_raises_projection_error()

        # Resume...
        with ProjectionRunner(
            application_class=Application[UUID],
            projection_class=AggregateEventCountersProjection,
            view_class=self.view_class,
            env=self.env,
        ) as runner:

            # Construct separate instance of "write model".
            write_model = Application[UUID](self.env)

            # Construct separate instance of "read model".
            read_model = InfrastructureFactory.construct(
                env=Environment(
                    name=AggregateEventCountersProjection.name, env=self.env
                )
            ).tracking_recorder(self.view_class)

            # Still terminates with projection error.
            with self.assertRaises(SpannerThrownError):
                runner.run_forever()

            # Wait times out (event has not been processed).
            with self.assertRaises(TimeoutError):
                read_model.wait(
                    application_name=write_model.name,
                    notification_id=write_model.recorder.max_notification_id(),
                )

    def setUp(self) -> None:
        drop_tables()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()


del EventCountersViewTestCase
