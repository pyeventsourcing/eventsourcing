from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest

from eventsourcing.decorator import event, triggers
from eventsourcing.persistence import InfrastructureFactory, StoredEvent
from eventsourcing.postgres import PostgresApplicationRecorder
from eventsourcing.pydantic import Aggregate, AggregatesApplication
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import Environment, clear_topic_cache

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_benchmark.fixture import BenchmarkFixture

envs = {
    "popo": {
        "PERSISTENCE_MODULE": "eventsourcing.popo",
    },
    "sqlite": {
        "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        "SQLITE_DBNAME": ":memory:",
    },
    "postgres": {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
    },
    "postgres-text": {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
        "ORIGINATOR_ID_TYPE": "text",
    },
    "postgres-functions": {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
        "POSTGRES_ENABLE_DB_FUNCTIONS": "y",
    },
    "postgres-functions-and-text": {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
        "POSTGRES_ENABLE_DB_FUNCTIONS": "y",
        "ORIGINATOR_ID_TYPE": "text",
    },
}

param_arg_names = "env,num_events"
param_arg_values = [
    ("popo", 1),
    # # ("popo", 10),
    # ("popo", 100),
    ("sqlite", 1),
    # # ("sqlite", 10),
    # ("sqlite", 100),
    ("postgres", 1),
    # # ("postgres", 10),
    # ("postgres", 100),
    ("postgres-text", 1),
    # # ("postgres", 10),
    # ("postgres-text", 100),
    ("postgres-functions", 1),
    # # ("postgres", 10),
    # ("postgres-functions", 100),
    ("postgres-functions-and-text", 1),
    # # ("postgres", 10),
    # ("postgres-functions-and-text", 100),
]

rounds = {
    "popo": 5000,
    "sqlite": 3000,
    "postgres": 1000,
    "postgres-text": 1000,
    "postgres-functions": 1000,
    "postgres-functions-and-text": 1000,
}


@pytest.mark.parametrize("num_events", [1, 100])
@pytest.mark.benchmark(group="construct-stored-event")
def test_stored_event(num_events: int, benchmark: BenchmarkFixture) -> None:
    originator_id = str(uuid4())

    def func() -> None:
        _ = [
            StoredEvent(
                originator_id=originator_id,
                originator_version=i + 1,
                topic="topic1",
                state=b"state1",
            )
            for i in range(num_events)
        ]

    benchmark(func)


@pytest.mark.parametrize("num_events", [1, 100])
@pytest.mark.benchmark(group="new-uuid4")
def test_uuid4(num_events: int, benchmark: BenchmarkFixture) -> None:
    def func() -> None:
        _ = [uuid4() for i in range(num_events)]

    benchmark(func)


@pytest.mark.parametrize(param_arg_names, param_arg_values)
@pytest.mark.benchmark(group="recorder-insert-events-1")
def test_recorder_insert_events_1(
    env: str, num_events: int, benchmark: BenchmarkFixture
) -> None:
    recorder = InfrastructureFactory.construct(
        env=Environment(name="benchmark", env=envs[env])
    ).application_recorder()

    def setup() -> Any:
        # TODO: Maybe come back to supporting `str | UUID` in StoredEvent.
        originator_id: str | UUID = "test-" + str(uuid4()) if "text" in env else uuid4()
        events = [
            StoredEvent(
                originator_id=cast(str, originator_id),
                originator_version=i + 1,
                topic="topic1",
                state=b"state1",
            )
            for i in range(num_events)
        ]
        return (events,), dict[Any, Any]()

    def func(events: Sequence[StoredEvent]) -> None:
        recorder.insert_events(events)

    try:
        benchmark.pedantic(func, setup=setup, rounds=rounds[env])
    finally:
        if isinstance(recorder, PostgresApplicationRecorder):
            drop_tables()


@pytest.mark.parametrize(param_arg_names, param_arg_values)
@pytest.mark.benchmark(group="recorder-insert-events-2")
def test_recorder_insert_events_2(
    env: str, num_events: int, benchmark: BenchmarkFixture
) -> None:
    recorder = InfrastructureFactory.construct(
        env=Environment(name="benchmark", env=envs[env])
    ).application_recorder()

    num_events *= 2

    def setup() -> Any:
        # TODO: Maybe come back to supporting `str | UUID` in StoredEvent.
        originator_id: str | UUID = "test-" + str(uuid4()) if "text" in env else uuid4()

        events = [
            StoredEvent(
                originator_id=cast(str, originator_id),
                originator_version=i + 1,
                topic="topic1",
                state=b"state1",
            )
            for i in range(num_events)
        ]
        return (events,), dict[Any, Any]()

    def func(events: Sequence[StoredEvent]) -> None:
        recorder.insert_events(events)

    try:
        benchmark.pedantic(func, setup=setup, rounds=rounds[env])
    finally:
        if isinstance(recorder, PostgresApplicationRecorder):
            drop_tables()


@pytest.mark.parametrize(param_arg_names, param_arg_values)
@pytest.mark.benchmark(group="recorder-insert-events-100")
def test_recorder_insert_events_100(
    env: str, num_events: int, benchmark: BenchmarkFixture
) -> None:
    factory: InfrastructureFactory[Any] = InfrastructureFactory.construct(
        env=Environment(name="benchmark", env=envs[env])
    )
    recorder = factory.application_recorder()

    num_events *= 100

    def setup() -> Any:
        originator_id: str = "test-" + str(uuid4())

        events = [
            StoredEvent(
                originator_id=originator_id,
                originator_version=i + 1,
                topic="topic1",
                state=b"state1",
            )
            for i in range(num_events)
        ]
        return (events,), dict[Any, Any]()

    def func(events: Sequence[StoredEvent]) -> None:
        recorder.insert_events(events)

    try:
        benchmark.pedantic(func, setup=setup, rounds=int(rounds[env] / 10))
    finally:
        if isinstance(recorder, PostgresApplicationRecorder):
            drop_tables()


@pytest.mark.parametrize(param_arg_names, param_arg_values)
@pytest.mark.benchmark(group="recorder-select-events")
def test_recorder_select_events(
    env: str, num_events: int, benchmark: BenchmarkFixture
) -> None:
    factory: InfrastructureFactory[Any] = InfrastructureFactory.construct(
        env=Environment(name="benchmark", env=envs[env])
    )
    recorder = factory.application_recorder()

    if "text" in env or "functions" in env:
        pytest.skip("nothing to do")

    originator_id = str(uuid4())

    events = [
        StoredEvent(
            originator_id=originator_id,
            originator_version=i + 1,
            topic="topic1",
            state=b"state1",
        )
        for i in range(num_events)
    ]

    recorder.insert_events(events)

    def func() -> None:
        recorder.select_events(originator_id)

    try:
        benchmark(func)
    finally:
        if isinstance(recorder, PostgresApplicationRecorder):
            drop_tables()


@pytest.mark.parametrize(param_arg_names, param_arg_values)
@pytest.mark.benchmark(group="call-app-save")
def test_app_save(env: str, num_events: int, benchmark: BenchmarkFixture) -> None:

    if "text" in env:
        pytest.skip("Skipping test (text IDs not supported by test)")

    app = AggregatesApplication(env=envs[env])

    clear_topic_cache()

    class A(Aggregate):
        @event("Created")
        def __init__(self, a: int):
            self.a = a

        @event("Continued")
        def subsequent(self, a: int) -> None:
            self.a = a

    def setup() -> Any:
        agg = A(a=0)
        for i in range(num_events - 1):
            agg.subsequent(a=i + 1)
        return (app, agg), dict[Any, Any]()

    def func(app: AggregatesApplication, agg: Aggregate) -> None:
        app.save(agg)

    try:
        benchmark.pedantic(func, setup=setup, rounds=rounds[env])
    finally:
        if isinstance(app.recorder, PostgresApplicationRecorder):
            drop_tables()


@pytest.mark.parametrize(param_arg_names, param_arg_values)
@pytest.mark.benchmark(group="call-app-command")
def test_app_command(env: str, num_events: int, benchmark: BenchmarkFixture) -> None:

    if "text" in env:
        pytest.skip("Skipping test (text IDs not supported by test)")

    class A(Aggregate):
        @event("Created")
        def __init__(self, a: int):
            self.a = a

        @event("Continued")
        def subsequent(self, a: int) -> None:
            self.a = a

    class MyApplication(AggregatesApplication):
        def command(self) -> None:
            agg = A(a=0)
            for i in range(num_events - 1):
                agg.subsequent(a=i + 1)
            self.save(agg)

    app = MyApplication(env=envs[env])

    clear_topic_cache()

    try:
        benchmark(app.command)
    finally:
        if isinstance(app.recorder, PostgresApplicationRecorder):
            drop_tables()


@pytest.mark.parametrize(param_arg_names, param_arg_values)
@pytest.mark.benchmark(group="call-repository-get")
def test_repository_get(env: str, num_events: int, benchmark: BenchmarkFixture) -> None:

    if "text" in env:
        pytest.skip("Skipping test (text IDs not supported by test)")

    clear_topic_cache()

    class A(Aggregate):
        @triggers("Created")
        def __init__(self, a: int):
            self.a = a

        @triggers("Continued")
        def subsequent(self, a: int) -> None:
            self.a = a

    app = AggregatesApplication(env=envs[env])
    agg = A(a=0)
    for i in range(num_events - 1):
        agg.subsequent(a=i + 1)
    app.save(agg)

    def func() -> None:
        app.repository.get(agg.id, A)

    try:
        benchmark(func)
    finally:
        if isinstance(app.recorder, PostgresApplicationRecorder):
            drop_tables()
