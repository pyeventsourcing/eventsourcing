from __future__ import annotations

from typing import Any, ClassVar, override
from uuid import uuid4

from psycopg.sql import SQL, Identifier

from eventsourcing.msgspec import AggregatesApplication
from eventsourcing.persistence import (
    InfrastructureFactory,
    Tracking,
)
from eventsourcing.postgres import (
    PostgresDatastore,
    PostgresTrackingRecorder,
)
from eventsourcing.projection import (
    ProjectionRunner,
)
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.tests.projection import (
    AggregateEventProjectionTestCase,
    SpannerThrownError,
    StudentAggregate,
    StudentAnalyticsEventProcessor,
    StudentAnalyticsView,
    StudentAnalyticsViewTestCase,
)
from eventsourcing.utils import Environment


class PostgresStudentAnalyticsView(PostgresTrackingRecorder, StudentAnalyticsView):
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

    @override
    def get_student_registered_counter(self) -> int:
        return self._select_counter(self._created_event_counter_name)

    @override
    def get_student_name_changed_counter(self) -> int:
        return self._select_counter(self._subsequent_event_counter_name)

    @override
    def incr_student_registered_counter(self, tracking: Tracking) -> None:
        self._incr_counter(self._created_event_counter_name, tracking)

    @override
    def incr_student_name_changed_counter(self, tracking: Tracking) -> None:
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


class TestPostgresStudentAnalytics(StudentAnalyticsViewTestCase):
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

    @override
    def setUp(self) -> None:
        self.factory = InfrastructureFactory[StudentAnalyticsView].construct(self.env)

    @override
    def tearDown(self) -> None:
        self.factory.close()
        drop_tables()

    @override
    def construct_event_counters_view(self) -> StudentAnalyticsView:
        return self.factory.tracking_recorder(PostgresStudentAnalyticsView)


class TestAggregateEventProjectionWithPostgres(
    AggregateEventProjectionTestCase[PostgresStudentAnalyticsView]
):
    view_class = PostgresStudentAnalyticsView
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
    }

    @override
    def setUp(self) -> None:
        drop_tables()
        super().setUp()

    @override
    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()

    @override
    def test_event_counters_projection(self) -> None:
        super().test_event_counters_projection()

        # Resume....
        with ProjectionRunner(
            application_class=AggregatesApplication,
            projection_class=StudentAnalyticsEventProcessor,
            view_class=self.view_class,
            env=self.env,
        ):

            # Construct separate instance of "write model".
            write_model = AggregatesApplication(env=self.env)

            # Construct separate instance of "read model".
            factory: InfrastructureFactory[StudentAnalyticsView] = (
                InfrastructureFactory.construct(
                    env=Environment(
                        name=StudentAnalyticsEventProcessor.name, env=self.env
                    )
                )
            )
            read_model = factory.tracking_recorder(self.view_class)

            # Write some events.
            aggregate = StudentAggregate(student_id=str(uuid4()))
            aggregate.change_name()
            aggregate.change_name()
            recordings = write_model.save(aggregate)

            # Wait for events to be processed.
            read_model.wait(
                context_name=write_model.context_name,
                notification_id=recordings[-1].notification.id,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 3)
            self.assertEqual(read_model.get_student_name_changed_counter(), 6)

            # Write some more events.
            aggregate = StudentAggregate(student_id=str(uuid4()))
            aggregate.change_name()
            aggregate.change_name()
            recordings = write_model.save(aggregate)

            # Wait for events to be processed.
            read_model.wait(
                context_name=write_model.context_name,
                notification_id=recordings[-1].notification.id,
            )

            # Query the read model.
            self.assertEqual(read_model.get_student_registered_counter(), 4)
            self.assertEqual(read_model.get_student_name_changed_counter(), 8)

    @override
    def test_run_forever_raises_projection_error(self) -> None:
        super().test_run_forever_raises_projection_error()

        # Resume...
        with ProjectionRunner(
            application_class=AggregatesApplication,
            projection_class=StudentAnalyticsEventProcessor,
            view_class=self.view_class,
            env=self.env,
        ) as runner:

            # Construct separate instance of "write model".
            write_model = AggregatesApplication(env=self.env)

            # Construct separate instance of "read model".
            factory: InfrastructureFactory[PostgresTrackingRecorder] = (
                InfrastructureFactory.construct(
                    env=Environment(
                        name=StudentAnalyticsEventProcessor.context_name, env=self.env
                    )
                )
            )
            read_model = factory.tracking_recorder(self.view_class)

            # Still terminates with projection error.
            with self.assertRaises(SpannerThrownError):
                runner.run_forever(timeout=5)

            # Wait times out (event has not been processed).
            with self.assertRaises(TimeoutError):
                read_model.wait(
                    context_name=write_model.context_name,
                    notification_id=write_model.recorder.max_notification_id(),
                )


del AggregateEventProjectionTestCase
del StudentAnalyticsViewTestCase
