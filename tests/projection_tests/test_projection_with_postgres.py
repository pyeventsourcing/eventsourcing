from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from psycopg.sql import SQL, Identifier

from eventsourcing.application import (
    Application,
)
from eventsourcing.domain import (
    Aggregate,
)
from eventsourcing.persistence import (
    InfrastructureFactory,
    Tracking,
)
from eventsourcing.postgres import (
    PostgresDatastore,
    PostgresFactory,
    PostgresTrackingRecorder,
)
from eventsourcing.projection import (
    ProjectionRunner,
)
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.tests.projection import (
    AggregateEventCountersProjection,
    AggregateEventCountersProjectionTestCase,
    EventCountersInterface,
    EventCountersViewTestCase,
    SpannerThrownError,
)
from eventsourcing.utils import Environment


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


class TestEventCountersViewWithPostgres(EventCountersViewTestCase):
    expected_factory_topic = "eventsourcing.postgres:PostgresFactory"
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
        "POSTGRES_SCHEMA": "public",
    }

    def setUp(self) -> None:
        self.factory = PostgresFactory(self.env)

    def tearDown(self) -> None:
        self.factory.close()
        drop_tables()

    def construct_event_counters_view(self) -> EventCountersInterface:
        return self.factory.tracking_recorder(PostgresEventCounters)


class TestAggregateEventCountersProjectionWithPostgres(
    AggregateEventCountersProjectionTestCase
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

    def setUp(self) -> None:
        drop_tables()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()

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


del AggregateEventCountersProjectionTestCase
del EventCountersViewTestCase
