from __future__ import annotations

from threading import Event, Thread
from time import sleep
from typing import TYPE_CHECKING, Any
from unittest import TestCase
from uuid import uuid4

import pytest

from eventsourcing.dcb.api import (
    DCBAppendCondition,
    DCBEvent,
    DCBQuery,
    DCBQueryItem,
    DCBReadResponse,
    DCBRecorder,
    DCBSequencedEvent,
    DCBSubscription,
)
from eventsourcing.persistence import IntegrityError, ProgrammingError
from eventsourcing.postgres import PostgresDatastore, PostgresRecorder
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import Environment
from examples.dcb_enrolment_with_basic_objects.postgres_ts import (
    PostgresDCBRecorderTS,
    PostgresTSDCBFactory,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from pytest_benchmark.fixture import BenchmarkFixture

    from eventsourcing.dcb.postgres_tt import PostgresDCBRecorderTT

# https://dcb.events/specification/


class TestDCBObjects(TestCase):
    def test_query_item(self) -> None:
        # Can have zero tags and zero items.
        item = DCBQueryItem()
        self.assertEqual([], item.types)
        self.assertEqual([], item.tags)

        # Can have more than zero types.
        item = DCBQueryItem(types=["EventType1", "EventType2"])
        self.assertEqual(["EventType1", "EventType2"], item.types)
        self.assertEqual([], item.tags)

        # Can have more than zero tags.
        item = DCBQueryItem(tags=["tag1", "tag2"])
        self.assertEqual([], item.types)
        self.assertEqual(["tag1", "tag2"], item.tags)

    def test_query(self) -> None:
        # Can have zero items.
        query = DCBQuery()
        self.assertEqual(0, len(query.items))

        # Can have more than zero items.
        query = DCBQuery(items=[DCBQueryItem(), DCBQueryItem()])
        self.assertEqual(2, len(query.items))

    def test_append_condition(self) -> None:
        query = DCBQuery()
        # Must have one "fail if events match" query.
        condition = DCBAppendCondition(fail_if_events_match=query)
        self.assertEqual(query, condition.fail_if_events_match)
        self.assertEqual(None, condition.after)

        # May have an integer "after" value.
        condition = DCBAppendCondition(fail_if_events_match=query, after=12)
        self.assertEqual(query, condition.fail_if_events_match)
        self.assertEqual(12, condition.after)

    def test_event(self) -> None:
        # Must contain "type" and "data".
        uuid = str(uuid4())
        event = DCBEvent(type="EventType1", data=b"data", uuid=uuid, metadata={})
        self.assertEqual("EventType1", event.type)
        self.assertEqual(b"data", event.data)
        self.assertEqual([], event.tags)
        self.assertEqual(uuid, event.uuid)
        self.assertEqual({}, event.metadata)

        # May contain tags.
        event = DCBEvent(
            type="EventType1",
            data=b"data",
            tags=["tag1", "tag2"],
            uuid=str(uuid4()),
            metadata={},
        )
        self.assertEqual("EventType1", event.type)
        self.assertEqual(b"data", event.data)
        self.assertEqual(["tag1", "tag2"], event.tags)

    def test_sequenced_event(self) -> None:
        sequenced_event = DCBSequencedEvent(
            event=DCBEvent(
                type="EventType1", data=b"data", uuid=str(uuid4()), metadata={}
            ),
            position=3,
        )
        self.assertEqual("EventType1", sequenced_event.event.type)
        self.assertEqual(b"data", sequenced_event.event.data)
        self.assertEqual(3, sequenced_event.position)


class TestDCBSubscription(TestCase):
    def test(self) -> None:
        class MyRecorder(DCBRecorder):

            def subscribe(
                self, query: DCBQuery | None = None, *, after: int | None = None
            ) -> DCBSubscription[MyRecorder]:
                raise NotImplementedError

            def append(
                self,
                events: Sequence[DCBEvent],
                condition: DCBAppendCondition | None = None,
            ) -> int:
                raise NotImplementedError

            def read(
                self,
                query: DCBQuery | None = None,
                *,
                after: int | None = None,
                limit: int | None = None,
            ) -> DCBReadResponse:
                raise NotImplementedError

        class MySubscription(DCBSubscription[MyRecorder]):
            def __next__(self) -> DCBSequencedEvent:
                raise NotImplementedError

        s = MySubscription(
            recorder=MyRecorder(),
            query=None,
            after=None,
        )
        with self.assertRaises(ProgrammingError):
            s.__exit__()

        s.__enter__()

        with self.assertRaises(ProgrammingError):
            s.__enter__()

        self.assertEqual(s, iter(s))


class WithPostgres(TestCase):
    postgres_dcb_recorder_class: type[PostgresDCBRecorderTT | PostgresDCBRecorderTS]
    pool_size: int = 1

    def setUp(self) -> None:
        drop_tables()
        self.datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port=5432,
            user="eventsourcing",
            password="eventsourcing",  # noqa:  S106
            pool_size=self.pool_size,
        )
        self.recorder = self.postgres_dcb_recorder_class(self.datastore)
        self.recorder.create_table()

    def tearDown(self) -> None:
        self.datastore.close()
        # Drop tables.
        drop_tables()


class TestDCBPostgresFactory(TestCase):
    def test(self) -> None:
        # For now, just cover the case of not creating a table.
        factory = PostgresTSDCBFactory(
            Environment(
                name="test",
                env={
                    "POSTGRES_DBNAME": "eventsourcing",
                    "POSTGRES_HOST": "localhost",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_USER": "eventsourcing",
                    "POSTGRES_PASSWORD": "eventsourcing",
                    "CREATE_TABLE": "f",
                },
            )
        )
        recorder = factory.dcb_recorder()
        self.assertIsInstance(recorder, PostgresRecorder)


class ConcurrentAppendTestCase(TestCase):
    insert_num = 10000

    def _test_commit_vs_insert_order(self, event_store: DCBRecorder) -> None:
        race_started = Event()

        tag1 = str(uuid4())
        tag2 = str(uuid4())

        stack1 = self.create_stack(tag1)
        stack2 = self.create_stack(tag2)

        errors = []

        def append_stack(stack: list[DCBEvent]) -> None:
            try:
                race_started.wait()
                event_store.append(stack)
            except Exception as e:
                errors.append(e)

        thread1 = Thread(target=append_stack, args=(stack1,), daemon=True)
        thread2 = Thread(target=append_stack, args=(stack2,), daemon=True)

        thread1.start()
        thread2.start()

        sleep(0.1)

        race_started.set()

        thread1.join()
        thread2.join()

        if errors:
            raise errors[0]

        # sleep(1)  # Added to make eventsourcing-axon tests work.
        sequenced_events = list(event_store.read())
        positions_for_tag1 = [
            s.position for s in sequenced_events if tag1 in s.event.tags
        ]
        positions_for_tag2 = [
            s.position for s in sequenced_events if tag2 in s.event.tags
        ]
        self.assertEqual(self.insert_num, len(positions_for_tag1))
        self.assertEqual(self.insert_num, len(positions_for_tag2))

        max_position_for_tag1 = max(positions_for_tag1)
        max_position_for_tag2 = max(positions_for_tag2)
        min_position_for_tag1 = min(positions_for_tag1)
        min_position_for_tag2 = min(positions_for_tag2)

        if max_position_for_tag1 > min_position_for_tag2:
            self.assertGreater(min_position_for_tag1, max_position_for_tag2)
        else:
            self.assertGreater(min_position_for_tag2, max_position_for_tag1)

    def _test_fail_condition_is_effective(self, event_store: DCBRecorder) -> None:
        race_started = Event()

        tag1 = str(uuid4())
        tag2 = str(uuid4())

        stack1 = self.create_stack(tag1)
        stack2 = self.create_stack(tag2)

        errors = []

        def append_stack(stack: list[DCBEvent]) -> None:
            try:
                race_started.wait()
                event_store.append(stack, DCBAppendCondition(after=0))
            except Exception as e:
                errors.append(e)

        thread1 = Thread(target=append_stack, args=(stack1,), daemon=True)
        thread2 = Thread(target=append_stack, args=(stack2,), daemon=True)

        thread1.start()
        thread2.start()

        sleep(0.1)

        race_started.set()

        thread1.join()
        thread2.join()

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], IntegrityError)

        sequenced_events = list(event_store.read())
        positions_for_tag1 = [
            s.position for s in sequenced_events if tag1 in s.event.tags
        ]
        positions_for_tag2 = [
            s.position for s in sequenced_events if tag2 in s.event.tags
        ]

        if len(positions_for_tag1) == self.insert_num:
            self.assertEqual(len(positions_for_tag2), 0)
        elif len(positions_for_tag2) == self.insert_num:
            self.assertEqual(len(positions_for_tag1), 0)
        else:
            self.fail(
                f"Inserted {len(positions_for_tag1)} for tag1 "
                f"and {len(positions_for_tag2)} for tag2"
            )

    def create_stack(self, tag: str) -> list[DCBEvent]:
        return [
            DCBEvent(
                type="CommitOrderTest",
                data=b"",
                tags=[tag],
                uuid=str(uuid4()),
                metadata={},
            )
            for _ in range(self.insert_num)
        ]


@pytest.fixture
def eventstore() -> Iterator[DCBRecorder]:
    datastore = PostgresDatastore(
        dbname="eventsourcing",
        host="127.0.0.1",
        port=5432,
        user="eventsourcing",
        password="eventsourcing",  # noqa:  S106
    )
    recorder = PostgresDCBRecorderTS(datastore)
    recorder.create_table()
    yield recorder

    drop_tables()


@pytest.mark.benchmark(group="dcb-append-one-event")
def test_recorder_append_one_event(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:

    def setup() -> Any:
        events = generate_events(1)
        return (events,), {}

    class Context:
        position: int = 0

    def func(events: list[DCBEvent]) -> None:
        Context.position = eventstore.append(
            events,
            DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[DCBQueryItem(tags=events[0].tags)]
                ),
                after=Context.position,
            ),
        )

    benchmark.pedantic(func, setup=setup, rounds=500)


@pytest.mark.benchmark(group="dcb-append-ten-events")
def test_recorder_append_ten_events(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:

    def setup() -> Any:
        events = generate_events(10)
        return (events,), {}

    class Context:
        position: int = 0

    def func(events: list[DCBEvent]) -> None:
        Context.position = eventstore.append(
            events,
            DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[DCBQueryItem(tags=events[0].tags)]
                ),
                after=Context.position,
            ),
        )

    benchmark.pedantic(func, setup=setup, rounds=500)


@pytest.mark.benchmark(group="dcb-read-events-no-query-limit-ten")
def test_recorder_read_events_no_query_limit_ten(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)

    def func() -> None:
        results = eventstore.read(limit=10)
        assert len(list(results)) == 10

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-no-query-after-thousand-limit-ten")
def test_recorder_read_events_no_query_after_thousand_limit_ten(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)

    def func() -> None:
        results = eventstore.read(after=1000, limit=10)
        assert len(list(results)) == 10

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-one-query-one-type")
def test_recorder_read_events_one_query_one_type(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)

    query = DCBQuery(items=[DCBQueryItem(types=[events[-1].type])])

    def func() -> None:
        results = eventstore.read(query)
        assert len(list(results)) == 1

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-two-queries-one-type")
def test_recorder_read_events_two_queries_one_type(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)

    query = DCBQuery(
        items=[
            DCBQueryItem(types=[events[0].type]),
            DCBQueryItem(types=[events[-1].type]),
        ],
    )

    def func() -> None:
        results = eventstore.read(query)
        assert len(list(results)) == 2

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-one-query-two-types")
def test_recorder_read_events_one_query_two_types(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)

    query = DCBQuery(
        items=[
            DCBQueryItem(
                types=[
                    events[0].type,
                    events[-1].type,
                ]
            )
        ]
    )

    def func() -> None:
        results = eventstore.read(query)
        assert len(list(results)) == 2

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-one-query-one-tag")
def test_recorder_read_events_one_query_one_tag(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)
    query = DCBQuery(items=[DCBQueryItem(tags=events[-1].tags)])

    def func() -> None:
        results = eventstore.read(query)
        assert len(list(results)) == 1

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-two-queries-one-tag")
def test_recorder_read_events_two_queries_one_tag(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)
    query = DCBQuery(
        items=[
            DCBQueryItem(tags=events[0].tags),
            DCBQueryItem(tags=events[-1].tags),
        ]
    )

    def func() -> None:
        results = eventstore.read(query)
        assert len(list(results)) == 2

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-one-query-two-tags")
def test_recorder_read_events_one_query_two_tags(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)
    query = DCBQuery(
        items=[
            DCBQueryItem(tags=events[0].tags + events[-1].tags),
        ]
    )

    def func() -> None:
        read_response = eventstore.read(query)
        assert len(list(read_response)) == 0

    benchmark(func)


# class MySetupForRunningExplainAnalyzeInPsql(TestCase):
#     def setUp(self) -> None:
#         datastore = PostgresDatastore(
#             dbname="eventsourcing",
#             host="127.0.0.1",
#             port=5432,
#             user="eventsourcing",
#             password="eventsourcing",  # no qa:  S106
#             after_connect=PostgresDCBEventStoreTS.register_pg_composite_type_adapters,
#         )
#         self.eventstore = PostgresDCBEventStoreTS(datastore)
#         self.eventstore.create_table()
#
#     def test(self):
#         events = generate_events(500000)
#         self.eventstore.append(events)
#         self.eventstore.read()
#
#
#     def tearDown(self) -> None:
#         drop_tables()


def generate_events(num_events: int) -> list[DCBEvent]:
    return [
        DCBEvent(
            type=f"topic{i}",
            data=b"state{i}",
            tags=[str(uuid4())],
            uuid=str(uuid4()),
            metadata={},
        )
        for i in range(num_events)
    ]


useful_for_explain_analyse_functions_and_procedures = """
LOAD 'auto_explain';
SET auto_explain.log_nested_statements = ON; -- statements inside functions
SET auto_explain.log_min_duration = 1;       -- exclude very fast queries taking < 1 ms
-- SET auto_explain.log_analyze = ON;        -- log execution times, too? (expensive!)
"""

useful_for_listing_functions_and_procedures = """
select n.nspname as schema_name,
       p.proname as specific_name,
       case p.prokind
            when 'f' then 'FUNCTION'
            when 'p' then 'PROCEDURE'
            when 'a' then 'AGGREGATE'
            when 'w' then 'WINDOW'
            end as kind,
       l.lanname as language,
       case when l.lanname = 'internal' then p.prosrc
            else pg_get_functiondef(p.oid)
            end as definition,
       pg_get_function_arguments(p.oid) as arguments,
       t.typname as return_type
from pg_proc p
left join pg_namespace n on p.pronamespace = n.oid
left join pg_language l on p.prolang = l.oid
left join pg_type t on t.oid = p.prorettype
where n.nspname not in ('pg_catalog', 'information_schema')
order by schema_name,
         specific_name;
"""
