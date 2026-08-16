from __future__ import annotations

import locale
import signal
import subprocess
import sys
from typing import TYPE_CHECKING, Any, cast

from eventsourcing_umadb.recorders import UmaDbDcbRecorder
from psycopg.sql import SQL, Identifier

from eventsourcing.application import AggregatesApplication
from eventsourcing.dcb.application import DcbApplication
from eventsourcing.dcb.popo import InMemoryDcbRecorder
from eventsourcing.dcb.postgres_tt import (
    DB_FUNCTION_NAME_DCB_CONDITIONAL_APPEND_TT,
    DB_FUNCTION_NAME_DCB_UNCONDITIONAL_APPEND_TT,
    PostgresDcbRecorderTT,
)
from eventsourcing.errors import ProgrammingError
from eventsourcing.popo import POPOApplicationRecorder
from eventsourcing.postgres import PostgresApplicationRecorder, PostgresDatastore
from eventsourcing.timestamp import datetime_now_with_tzinfo
from examples.dcb_enrolment.application import EnrolmentWithAggregates
from examples.dcb_enrolment.interface import EnrolmentInterface
from examples.dcb_enrolment_with_basic_objects.application import (
    EnrolmentWithBasicDcbObjects,
)
from examples.dcb_enrolment_with_basic_objects.postgres_ts import (
    PG_FUNCTION_NAME_DCB_CHECK_APPEND_CONDITION_TS,
    PG_FUNCTION_NAME_DCB_INSERT_EVENTS_TS,
    PG_FUNCTION_NAME_DCB_SELECT_EVENTS_TS,
    PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS,
    PostgresDcbRecorderTS,
)
from examples.dcb_enrolment_with_enduring_objects.application import (
    EnrolmentWithEnduringObjects,
)
from examples.dcb_enrolment_with_vertical_slices.application import (
    EnrolmentWithVerticalSlices,
)

locale.setlocale(locale.LC_ALL, "")

if TYPE_CHECKING:
    from collections.abc import Iterator


env = {}
SPEEDRUN_DB_NAME = "course_subscriptions_speedrun"
# SPEEDRUN_DB_NAME = "course_subscriptions_speedrun_tt_new"
# SPEEDRUN_DB_NAME = "course_subscriptions_speedrun_tt3"
SPEEDRUN_DB_USER = "eventsourcing"
SPEEDRUN_DB_PASSWORD = "eventsourcing"  # noqa: S105

NUM_COURSES = 10
NUM_STUDENTS = 10
READING_ONLY = False


def inf_range() -> Iterator[int]:
    i = 1
    while True:
        yield i
        i += 1


config: dict[str, tuple[type[EnrolmentInterface], int, dict[str, str]]] = {
    "dcb-pg-ts": (
        EnrolmentWithBasicDcbObjects,
        # EnrolmentWithEnduringObjects,
        10,
        {
            "PERSISTENCE_MODULE": "examples.coursebookingdcb.postgres_ts",
            "POSTGRES_DBNAME": SPEEDRUN_DB_NAME,
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": SPEEDRUN_DB_USER,
            "POSTGRES_PASSWORD": SPEEDRUN_DB_PASSWORD,
            "POSTGRES_POOL_SIZE": "1",
            "POSTGRES_MAX_OVERFLOW": "0",
            "POSTGRES_MAX_WAITING": "0",
        },
    ),
    "dcb-pg-tt": (
        EnrolmentWithBasicDcbObjects,
        # EnrolmentWithEnduringObjects,
        10,
        {
            "PERSISTENCE_MODULE": "eventsourcing.dcb.postgres_tt",
            "POSTGRES_DBNAME": SPEEDRUN_DB_NAME,
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": SPEEDRUN_DB_USER,
            "POSTGRES_PASSWORD": SPEEDRUN_DB_PASSWORD,
            "POSTGRES_POOL_SIZE": "1",
            "POSTGRES_MAX_OVERFLOW": "0",
            "POSTGRES_MAX_WAITING": "0",
        },
    ),
    "dcb-pg-tt-slices": (
        EnrolmentWithVerticalSlices,
        10,
        {
            "PERSISTENCE_MODULE": "eventsourcing.dcb.postgres_tt",
            "POSTGRES_DBNAME": SPEEDRUN_DB_NAME,
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": SPEEDRUN_DB_USER,
            "POSTGRES_PASSWORD": SPEEDRUN_DB_PASSWORD,
            "POSTGRES_POOL_SIZE": "1",
            "POSTGRES_MAX_OVERFLOW": "0",
            "POSTGRES_MAX_WAITING": "0",
        },
    ),
    "dcb-umadb": (
        EnrolmentWithBasicDcbObjects,
        # EnrolmentWithEnduringObjects,
        10,
        {
            "PERSISTENCE_MODULE": "eventsourcing_umadb",
            "UMADB_URI": "http://127.0.0.1:50051",
        },
    ),
    "dcb-umadb-slices": (
        EnrolmentWithVerticalSlices,
        10,
        {
            "PERSISTENCE_MODULE": "eventsourcing_umadb",
            "UMADB_URI": "http://127.0.0.1:50051",
        },
    ),
    "dcb-mem": (
        EnrolmentWithEnduringObjects,
        100,
        {
            "PERSISTENCE_MODULE": "eventsourcing.dcb.popo",
        },
    ),
    "agg-pg": (
        EnrolmentWithAggregates,
        100,
        {
            "PERSISTENCE_MODULE": "eventsourcing.postgres",
            "POSTGRES_DBNAME": SPEEDRUN_DB_NAME,
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": SPEEDRUN_DB_USER,
            "POSTGRES_PASSWORD": SPEEDRUN_DB_PASSWORD,
            "POSTGRES_ENABLE_DB_FUNCTIONS": "y",
            "POSTGRES_POOL_SIZE": "1",
            "POSTGRES_MAX_OVERFLOW": "0",
            "POSTGRES_MAX_WAITING": "0",
            # "AGGREGATE_CACHE_MAXSIZE": "100",
            # "AGGREGATE_CACHE_FASTFORWARD": "f",
        },
    ),
    "agg-mem": (
        EnrolmentWithAggregates,
        1000,
        {
            "PERSISTENCE_MODULE": "eventsourcing.popo",
        },
    ),
}


interrupted = False


def set_signal_handler() -> None:

    def sigint_handler(*_: Any) -> None:
        global interrupted  # noqa: PLW0603
        interrupted = True

    signal.signal(signal.SIGINT, sigint_handler)


SQL_SELECT_COUNT_ROWS = SQL("SELECT COUNT(*) FROM {schema}.{table_name}")


def count_events(app: EnrolmentInterface) -> int:
    if isinstance(app, EnrolmentWithAggregates):
        recorder: Any = app.recorder
        if isinstance(recorder, PostgresApplicationRecorder):
            datastore = recorder.datastore
            statement = SQL_SELECT_COUNT_ROWS.format(
                schema=Identifier(datastore.schema),
                table_name=Identifier(recorder.events_table_name),
            )
            with datastore.get_connection() as conn:
                result = conn.execute(statement).fetchone()
                count = result["count"] if result is not None else 0
        elif isinstance(recorder, POPOApplicationRecorder):
            return recorder.max_notification_id() or 0
        else:
            msg = f"TODO implement counting rows for recorder: {type(recorder)}"
            raise NotImplementedError(msg)

    elif isinstance(
        app,
        (
            EnrolmentWithBasicDcbObjects,
            EnrolmentWithEnduringObjects,
            EnrolmentWithVerticalSlices,
        ),
    ):
        recorder = app.recorder
        if isinstance(recorder, (PostgresDcbRecorderTS, PostgresDcbRecorderTT)):
            datastore = recorder.datastore
            statement = SQL_SELECT_COUNT_ROWS.format(
                schema=Identifier(datastore.schema),
                table_name=Identifier(recorder.events_table_name),
            )
            with datastore.get_connection() as conn:
                result = conn.execute(statement).fetchone()
                count = result["count"] if result is not None else 0
        elif isinstance(recorder, UmaDbDcbRecorder):
            count = recorder.umadb.head() or 0
        else:
            assert isinstance(recorder, InMemoryDcbRecorder)
            count = len(recorder.events)
    else:
        msg = f"TODO implement counting rows for app type: {type(app)}"
        raise NotImplementedError(msg)

    return count


if __name__ == "__main__":
    cls: type[EnrolmentInterface]
    modes = [
        "dcb-pg-ts",
        "dcb-pg-tt",
        "dcb-pg-tt-slices",
        "dcb-umadb",
        "dcb-umadb-slices",
        "dcb-mem",
        "agg-pg",
        "agg-mem",
        "help",
        "new-db",
        "drop-funcs",
        "new-plans",
        "psql",
    ]
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"
    if mode == "help" or mode not in modes:
        print(f"Usage: {sys.argv[0]} [{' | '.join(modes)}]")
        sys.exit(0)
    if len(sys.argv) > 2:
        try:
            speedrun_duration: int | None = int(cast(int, sys.argv[2]))
        except ValueError:
            print("Invalid duration:", sys.argv[2])
            sys.exit(1)
    else:
        speedrun_duration = None

    if mode == "new-db":
        with (
            PostgresDatastore(
                dbname="postgres",
                host="127.0.0.1",
                port=5432,
                user="postgres",
                password="postgres",  # noqa: S106
            ) as datastore,
            datastore.get_connection() as conn,
        ):
            statements = [
                SQL("DROP DATABASE IF EXISTS {db}").format(
                    db=Identifier(SPEEDRUN_DB_NAME)
                ),
                SQL("CREATE DATABASE {db}").format(db=Identifier(SPEEDRUN_DB_NAME)),
                SQL("ALTER DATABASE {db} OWNER TO {user}").format(
                    db=Identifier(SPEEDRUN_DB_NAME),
                    user=Identifier(SPEEDRUN_DB_USER),
                ),
            ]
            for statement in statements:
                print(f"{statement.as_string()};")
                conn.execute(statement)
            sys.exit(0)

    if mode == "drop-funcs":
        with PostgresDatastore(
            dbname=SPEEDRUN_DB_NAME,
            host="127.0.0.1",
            port=5432,
            user=SPEEDRUN_DB_USER,
            password=SPEEDRUN_DB_PASSWORD,
        ) as datastore:
            statement_template = SQL("DROP FUNCTION {schema}.{name}")
            function_names = [
                PG_FUNCTION_NAME_DCB_CHECK_APPEND_CONDITION_TS,
                PG_FUNCTION_NAME_DCB_INSERT_EVENTS_TS,
                PG_FUNCTION_NAME_DCB_SELECT_EVENTS_TS,
                PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS,
                DB_FUNCTION_NAME_DCB_UNCONDITIONAL_APPEND_TT,
                DB_FUNCTION_NAME_DCB_CONDITIONAL_APPEND_TT,
            ]
            for function_name in function_names:
                statement = statement_template.format(
                    schema=Identifier("public"),
                    name=Identifier(function_name),
                )
                print(statement.as_string())
                try:
                    with datastore.get_connection() as conn:
                        conn.execute(statement)
                except ProgrammingError as e:
                    print(f"Function '{function_name}' not found:", e)
            procedure_names = [
                PG_PROCEDURE_NAME_DCB_APPEND_EVENTS_TS,
            ]
            statement_template = SQL("DROP PROCEDURE {name}")
            for function_name in function_names:
                for procedure_name in procedure_names:
                    statement = statement_template.format(
                        schema=Identifier("public"),
                        name=Identifier(procedure_name),
                    )
                    print(statement.as_string())
                    try:
                        with datastore.get_connection() as conn:
                            conn.execute(statement)
                    except ProgrammingError as e:
                        print(f"Procedure '{function_name}' not found:", e)
        sys.exit(0)

    if mode == "new-plans":
        with (
            PostgresDatastore(
                dbname="postgres",
                host="127.0.0.1",
                port=5432,
                user=SPEEDRUN_DB_USER,
                password=SPEEDRUN_DB_PASSWORD,
            ) as datastore,
            datastore.get_connection() as conn,
        ):
            discard_statement = SQL("DISCARD PLANS")
            print(discard_statement.as_string())
            conn.execute(discard_statement)
            sys.exit(0)

    if mode == "psql":
        subprocess.run(  # noqa: S603
            ["psql", "--dbname", SPEEDRUN_DB_NAME], check=True  # noqa: S607
        )
        sys.exit(0)

    if mode not in modes:
        print(f"Unknown mode: {mode}. Usage: {sys.argv[0]} [{' | '.join(modes)}]")
        sys.exit(1)
    cls, reporting_interval, extra_env = config[mode]
    env.update(extra_env)
    print()
    print(" Dynamic Consistency Boundaries Speed Run: Course Subscriptions")
    print(" ==============================================================")
    print()
    ops_per_iteration = NUM_COURSES + NUM_STUDENTS + NUM_COURSES * NUM_STUDENTS
    print(
        f" Per iteration: {NUM_COURSES} courses,"
        f" {NUM_STUDENTS} students ({ops_per_iteration} ops)"
    )
    print()
    print(f" Running '{mode}' mode: {cls.__name__}")
    for key, value in env.items():
        print(f"     {key}: {value}")
    print()
    # print(f"Reporting interval: every {reporting_interval} iterations...")
    # print()

    with cast(type[AggregatesApplication[Any] | DcbApplication[Any]], cls)(
        env=env
    ) as app_:

        app = cast(EnrolmentInterface, app_)

        started_event_count = count_events(app)
        print(f" Events in database at start:  {started_event_count:,d} events")
        print()

        if speedrun_duration is not None:
            print(f" Stopping after: {speedrun_duration}s")
            print()

        set_signal_handler()

        r_students = inf_range()
        r_courses = inf_range()

        started_script = datetime_now_with_tzinfo()
        started_report = datetime_now_with_tzinfo()
        report_counter = 0
        total_ops = 0
        report_ops = 0
        for i in inf_range():
            if interrupted:
                print()
                total_timedelta = datetime_now_with_tzinfo() - started_script
                total_seconds = total_timedelta.total_seconds()
                finished_event_count = count_events(app)
                num_new = finished_event_count - started_event_count
                print(
                    f" Events in database at end:  "
                    f"{finished_event_count:,d} events  "
                    f"({num_new :,d} new, {int(num_new / total_seconds):n}/s)"
                )
                print()
                # print(" Interrupted, stopping...")
                print()
                break
            course_ids = []
            for _ in range(NUM_COURSES):
                course_ids.append(
                    app.register_course(f"course-{next(r_courses)}", NUM_STUDENTS)
                )
                report_ops += 1
                if interrupted:
                    break
            student_ids = []
            for _ in range(NUM_STUDENTS):
                student_ids.append(
                    app.register_student(f"student-{next(r_students)}", NUM_COURSES)
                )
                report_ops += 1
                if interrupted:
                    break

            for course_id in course_ids:
                for student_id in student_ids:
                    app.join_course(student_id, course_id)
                    report_ops += 1
                    if interrupted:
                        break
                if interrupted:
                    break

            total_timedelta = datetime_now_with_tzinfo() - started_script
            total_seconds = total_timedelta.total_seconds()
            if total_seconds / (report_counter + 1) > 1:
                report_counter += 1
                total_ops += report_ops
                report_timedelta = (
                    datetime_now_with_tzinfo() - started_report
                ).total_seconds()
                report_rate = report_ops / report_timedelta
                print(
                    f" [{str(total_timedelta).split('.')[0]}s] ",
                    f"{i:>8} iterations ",
                    f"{total_ops:>8} ops ",
                    f"{int(1000000 / report_rate):>7} μs/op",
                    f"{int(report_rate):>7} ops/s ",
                )
                report_ops = 0
                started_report = datetime_now_with_tzinfo()

            if speedrun_duration is not None and total_seconds > speedrun_duration:
                print()
                finished_event_count = count_events(app)
                num_new = finished_event_count - started_event_count
                print(
                    f" Events in database at end:  "
                    f"{finished_event_count:,d} events  "
                    f"({num_new :,d} new, {int(num_new / total_seconds):n}/s)"
                )
                print()
                break
