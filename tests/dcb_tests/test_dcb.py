from __future__ import annotations

import json
from threading import Event, Thread
from time import sleep
from typing import TYPE_CHECKING, Any, cast
from unittest import TestCase
from uuid import uuid4

import pytest

from eventsourcing.dcb.api import (
    DCBAppendCondition,
    DCBEvent,
    DCBQuery,
    DCBQueryItem,
    DCBRecorder,
    DCBSequencedEvent,
)
from eventsourcing.dcb.popo import InMemoryDCBRecorder
from eventsourcing.dcb.postgres_tt import PostgresDCBRecorderTT
from eventsourcing.persistence import IntegrityError, ProgrammingError
from eventsourcing.postgres import PostgresDatastore, PostgresRecorder
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import Environment
from examples.coursebookingdcb.postgres_ts import (
    PostgresDCBRecorderTS,
    PostgresTSDCBFactory,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_benchmark.fixture import BenchmarkFixture


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
        event = DCBEvent(type="EventType1", data=b"data")
        self.assertEqual("EventType1", event.type)
        self.assertEqual(b"data", event.data)
        self.assertEqual([], event.tags)

        # May contain tags.
        event = DCBEvent(type="EventType1", data=b"data", tags=["tag1", "tag2"])
        self.assertEqual("EventType1", event.type)
        self.assertEqual(b"data", event.data)
        self.assertEqual(["tag1", "tag2"], event.tags)

    def test_sequenced_event(self) -> None:
        sequenced_event = DCBSequencedEvent(
            event=DCBEvent(type="EventType1", data=b"data"),
            position=3,
        )
        self.assertEqual("EventType1", sequenced_event.event.type)
        self.assertEqual(b"data", sequenced_event.event.data)
        self.assertEqual(3, sequenced_event.position)


class DCBRecorderTestCase(TestCase):

    def _test_event_store(self, eventstore: DCBRecorder) -> None:
        # Read all, expect no results.
        result, head = eventstore.read()
        self.assertEqual(0, len(list(result)))
        self.assertIsNone(head)

        # Append one event.
        event1 = DCBEvent(type="type1", data=b"data1", tags=["tagX"])
        position = eventstore.append(events=[event1])

        # Check the returned position is 1.
        self.assertEqual(1, position)

        # Read all, expect one event.
        result, head = eventstore.read()
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1, head)

        # Read all after 1, expect no events.
        result, head = eventstore.read(after=1)
        self.assertEqual(0, len(result))
        self.assertEqual(1, head)

        # Read all limit 1, expect one event.
        result, head = eventstore.read(limit=1)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1, head)

        # Read all limit 0, expect no events (and head is None).
        result, head = eventstore.read(limit=0)
        self.assertEqual(0, len(result))
        self.assertEqual(None, head)

        # Read events with type1, expect 1 event.
        query_type1 = DCBQuery(items=[DCBQueryItem(types=["type1"])])
        result, head = eventstore.read(query_type1)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1, head)

        # Read events with type2, expect no events.
        query_type2 = DCBQuery(items=[DCBQueryItem(types=["type2"])])
        result, head = eventstore.read(query_type2)
        self.assertEqual(0, len(result))
        self.assertEqual(1, head)

        # Read events with tagX, expect one event.
        query_tag_x = DCBQuery(items=[DCBQueryItem(tags=["tagX"])])
        result, head = eventstore.read(query_tag_x)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1, head)

        # Read events with tagY, expect no events.
        query_tag_y = DCBQuery(items=[DCBQueryItem(tags=["tagY"])])
        result, head = eventstore.read(query=query_tag_y)
        self.assertEqual(0, len(result))
        self.assertEqual(1, head)

        # Read events with type1 and tagX, expect one event.
        query_type1_tag_x = DCBQuery(
            items=[DCBQueryItem(types=["type1"], tags=["tagX"])]
        )
        result, head = eventstore.read(query=query_type1_tag_x)
        self.assertEqual(1, len(result))
        self.assertEqual(1, head)

        # Read events with type1 and tagY, expect no events.
        query_type1_tag_y = DCBQuery(
            items=[DCBQueryItem(types=["type1"], tags=["tagY"])]
        )
        result, head = eventstore.read(query=query_type1_tag_y)
        self.assertEqual(0, len(result))
        self.assertEqual(1, head)

        # Read events with type2 and tagX, expect no events.
        query_type2_tag_x = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagX"])]
        )
        result, head = eventstore.read(query=query_type2_tag_x)
        self.assertEqual(0, len(result))
        self.assertEqual(1, head)

        # Append two more events.
        event2 = DCBEvent(type="type2", data=b"data2", tags=["tagA", "tagB"])
        event3 = DCBEvent(type="type3", data=b"data3", tags=["tagA", "tagC"])
        position = eventstore.append(events=[event2, event3])

        # Check the returned position is 3
        self.assertEqual(3, position)

        # Read all, expect 3 events (in ascending order).
        result, head = eventstore.read()
        self.assertEqual(3, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(event2.data, result[1].event.data)
        self.assertEqual(event3.data, result[2].event.data)
        self.assertEqual(3, head)

        # Read all after 1, expect two events.
        result, head = eventstore.read(after=1)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3, head)

        # Read all after 2, expect one event.
        result, head = eventstore.read(after=2)
        self.assertEqual(1, len(result))
        self.assertEqual(event3.data, result[0].event.data)
        self.assertEqual(3, head)

        # Read all after 1, limit 1, expect one event.
        result, head = eventstore.read(after=1, limit=1)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(2, head)

        # Read type1 after 1, expect no events.
        result, head = eventstore.read(query_type1, after=1)
        self.assertEqual(0, len(result))
        self.assertEqual(3, head)

        # Read tagX after 1, expect no events.
        result, head = eventstore.read(query_tag_x, after=1)
        self.assertEqual(0, len(result))
        self.assertEqual(3, head)

        # Read type1 and tagX after 1, expect no events.
        result, head = eventstore.read(query_type1_tag_x, after=1)
        self.assertEqual(0, len(result))
        self.assertEqual(3, head)

        # Read events with tagA, expect two events.
        query_tag_a = DCBQuery(items=[DCBQueryItem(tags=["tagA"])])
        result, head = eventstore.read(query_tag_a)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3, head)

        # Read events with tagA and tagB, expect one event.
        query_tag_a_and_b = DCBQuery(items=[DCBQueryItem(tags=["tagA", "tagB"])])
        result, head = eventstore.read(query_tag_a_and_b)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(3, head)

        # Read events with tagB or tagC, expect two events.
        query_tag_b_or_c = DCBQuery(
            items=[
                DCBQueryItem(tags=["tagB"]),
                DCBQueryItem(tags=["tagC"]),
            ]
        )
        result, head = eventstore.read(query_tag_b_or_c)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3, head)

        # Read events with tagX or tagY, expect one event.
        query_tag_x_or_y = DCBQuery(
            items=[
                DCBQueryItem(tags=["tagX"]),
                DCBQueryItem(tags=["tagY"]),
            ]
        )
        result, head = eventstore.read(query_tag_x_or_y)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(3, head)

        # Read events with type2 and tagA, expect one event.
        query_type2_tag_a = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagA"])]
        )
        result, head = eventstore.read(query_type2_tag_a)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(3, head)

        # Read events with type2 and tagA after 2, expect no events.
        query_type2_tag_a = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagA"])]
        )
        result, head = eventstore.read(query_type2_tag_a, after=2)
        self.assertEqual(0, len(result))
        self.assertEqual(3, head)

        # Read events with type2 and tagA, expect one event.
        query_type2_tag_a = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagA"])]
        )
        result, head = eventstore.read(query_type2_tag_a)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(3, head)

        # Read events with type2 and tagB, or with type3 and tagC, expect two events.
        query_type2_tag_b_or_type3_tagc = DCBQuery(
            items=[
                DCBQueryItem(types=["type2"], tags=["tagB"]),
                DCBQueryItem(types=["type3"], tags=["tagC"]),
            ]
        )
        result, head = eventstore.read(query_type2_tag_b_or_type3_tagc)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3, head)

        # Repeat with query items in different order, expect events in ascending order.
        query_type3_tag_c_or_type2_tag_b = DCBQuery(
            items=[
                DCBQueryItem(types=["type3"], tags=["tagC"]),
                DCBQueryItem(types=["type2"], tags=["tagB"]),
            ]
        )
        result, head = eventstore.read(query_type3_tag_c_or_type2_tag_b)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3, head)

        # Append must fail if recorded events match condition.
        event4 = DCBEvent(type="type4", data=b"data4")

        # Fail because condition matches all.
        new = [event4]
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition())

        # Fail because condition matches all after 1.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(after=1))

        # Fail because condition matches type1.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_type1))

        # Fail because condition matches type2 after 1.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_type2, after=1))

        # Fail because condition matches tagX.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_tag_x))

        # Fail because condition matches tagA after 1.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_tag_a, after=1))

        # Fail because condition matches type1 and tagX.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_type1_tag_x))

        # Fail because condition matches type2 and tagA after 1.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_type2_tag_a, after=1))

        # Fail because condition matches tagA and tagB.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_tag_a_and_b))

        # Fail because condition matches tagB or tagC.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_tag_b_or_c))

        # Fail because condition matches tagX or tagY.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_tag_x_or_y))

        # Fail because condition matches with type2 and tagB, or with type3 and tagC.
        with self.assertRaises(IntegrityError):
            eventstore.append(new, DCBAppendCondition(query_type2_tag_b_or_type3_tagc))

        # Can append after 3.
        eventstore.append(new)

        # Can append match type_n.
        query_type_n = DCBQuery(items=[DCBQueryItem(types=["typeN"])])
        eventstore.append(new, DCBAppendCondition(query_type_n))

        # Can append match tagY.
        eventstore.append(new, DCBAppendCondition(query_tag_y))

        # Can append match type1 after 1.
        eventstore.append(new, DCBAppendCondition(query_type1, after=1))

        # Can append match tagX after 1.
        eventstore.append(new, DCBAppendCondition(query_tag_x, after=1))

        # Can append match type1 and tagX after 1.
        eventstore.append(new, DCBAppendCondition(query_type1_tag_x, after=1))

        # Can append match tagX, after 1.
        eventstore.append(new, DCBAppendCondition(query_tag_x, after=1))

        # Check it works with course subscription consistency boundaries and events.

        student_id = f"student1-{uuid4()}"
        student_registered = DCBEvent(
            type="StudentRegistered",
            data=json.dumps({"name": "Student1", "max_courses": 10}).encode(),
            tags=[student_id],
        )
        course_id = f"course1-{uuid4()}"
        course_registered = DCBEvent(
            type="CourseRegistered",
            data=json.dumps({"name": "Course1", "places": 10}).encode(),
            tags=[course_id],
        )
        student_joined_course = DCBEvent(
            type="StudentJoinedCourse",
            data=json.dumps(
                {"student_id": student_id, "course_id": course_id}
            ).encode(),
            tags=[course_id, student_id],
        )

        eventstore.append(
            events=[student_registered],
            condition=DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[
                        DCBQueryItem(
                            tags=student_registered.tags, types=["StudentRegistered"]
                        )
                    ],
                ),
                after=3,
            ),
        )
        eventstore.append(
            events=[course_registered],
            condition=DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[DCBQueryItem(tags=course_registered.tags)],
                ),
                after=3,
            ),
        )
        eventstore.append(
            events=[student_joined_course],
            condition=DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[DCBQueryItem(tags=student_joined_course.tags)],
                ),
                after=3,
            ),
        )

        result, head = eventstore.read()
        self.assertEqual(13, len(result))
        self.assertEqual(result[-3].event.type, student_registered.type)
        self.assertEqual(result[-2].event.type, course_registered.type)
        self.assertEqual(result[-1].event.type, student_joined_course.type)
        self.assertEqual(result[-3].event.data, student_registered.data)
        self.assertEqual(result[-2].event.data, course_registered.data)
        self.assertEqual(result[-1].event.data, student_joined_course.data)
        self.assertEqual(result[-3].event.tags, student_registered.tags)
        self.assertEqual(result[-2].event.tags, course_registered.tags)
        self.assertEqual(result[-1].event.tags, student_joined_course.tags)
        self.assertEqual(13, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_registered.tags)],
            )
        )
        self.assertEqual(2, len(result))
        self.assertEqual(13, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=course_registered.tags)],
            )
        )
        self.assertEqual(2, len(result))
        self.assertEqual(13, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_joined_course.tags)],
            )
        )
        self.assertEqual(1, len(result))
        self.assertEqual(13, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_registered.tags)],
            ),
            after=2,
        )
        self.assertEqual(2, len(result))
        self.assertEqual(13, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=course_registered.tags)],
            ),
            after=2,
        )
        self.assertEqual(2, len(result))
        self.assertEqual(13, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_joined_course.tags)],
            ),
            after=2,
        )
        self.assertEqual(1, len(result))
        self.assertEqual(13, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_registered.tags)],
            ),
            after=2,
            limit=1,
        )
        self.assertEqual(1, len(result))
        self.assertEqual(11, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=course_registered.tags)],
            ),
            after=2,
            limit=1,
        )
        self.assertEqual(1, len(result))
        self.assertEqual(12, head)

        result, head = eventstore.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_joined_course.tags)],
            ),
            after=2,
            limit=1,
        )
        self.assertEqual(1, len(result))
        self.assertEqual(13, head)

        consistency_boundary = DCBQuery(
            items=[
                DCBQueryItem(
                    types=["StudentRegistered", "StudentJoinedCourse"],
                    tags=[student_id],
                ),
                DCBQueryItem(
                    types=["CourseRegistered", "StudentJoinedCourse"],
                    tags=[course_id],
                ),
            ]
        )
        result, head = eventstore.read(
            query=consistency_boundary,
        )
        self.assertEqual(3, len(result))
        self.assertEqual(13, head)


class TestInMemoryDCBRecorder(DCBRecorderTestCase):
    def test_in_memory_event_store(self) -> None:
        self._test_event_store(InMemoryDCBRecorder())


class WithPostgres(TestCase):
    postgres_dcb_eventstore_class: type[PostgresDCBRecorderTT | PostgresDCBRecorderTS]

    def setUp(self) -> None:
        self.datastore = PostgresDatastore(
            dbname="eventsourcing",
            host="127.0.0.1",
            port=5432,
            user="eventsourcing",
            password="eventsourcing",  # noqa:  S106
        )
        self.eventstore = self.postgres_dcb_eventstore_class(self.datastore)
        self.eventstore.create_table()

    def tearDown(self) -> None:
        self.datastore.close()
        # Drop tables.
        drop_tables()


class TestPostgresDCBRecorderTS(DCBRecorderTestCase, WithPostgres):
    postgres_dcb_eventstore_class = PostgresDCBRecorderTS

    def test_postgres_event_store(self) -> None:
        self._test_event_store(self.eventstore)

    def test_pg_type_dcb_event(self) -> None:
        # Check "dcb_event" type.
        event = cast(PostgresDCBRecorderTS, self.eventstore).construct_pg_dcb_event(
            type="EventType1",
            data=b"data",
            tags=["tag1", "tag2"],
        )
        self.assertEqual("EventType1", event.type)
        self.assertEqual(b"data", event.data)
        self.assertEqual(["tag1", "tag2"], event.tags)

        with self.datastore.get_connection() as conn:
            result = conn.execute(
                (
                    "SELECT pg_typeof(%(dcb_event)s), "
                    "(%(dcb_event)s).type, "
                    "(%(dcb_event)s).data, "
                    "(%(dcb_event)s).tags"
                ),
                {"dcb_event": event},
            ).fetchone()

        assert result is not None
        self.assertEqual("dcb_event", result["pg_typeof"])
        self.assertEqual("EventType1", result["type"])
        self.assertEqual(b"data", result["data"])
        self.assertEqual(["tag1", "tag2"], result["tags"])

        with (
            self.assertRaises(ProgrammingError) as cm,
            self.datastore.get_connection() as conn,
        ):
            conn.execute(
                (
                    "SELECT pg_typeof(%(dcb_event)s), "
                    "(%(dcb_event)s).typeyyyyyyyyyyy, "
                    "(%(dcb_event)s).data, "
                    "(%(dcb_event)s).tags"
                ),
                {"dcb_event": event},
            ).fetchone()

        self.assertIn(
            'column "typeyyyyyyyyyyy" not found in data type dcb_event',
            str(cm.exception),
        )


class TestPostgresDCBRecorderTT(DCBRecorderTestCase, WithPostgres):
    postgres_dcb_eventstore_class = PostgresDCBRecorderTT

    def test_postgres_event_store(self) -> None:
        self._test_event_store(self.eventstore)


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
        recorder = factory.dcb_event_store()
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
        sequenced_events, head = event_store.read()
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

        sequenced_events, head = event_store.read()
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
            )
            for i in range(self.insert_num)
        ]


class TestPostgresDCBRecorderStoreTSCommitOrderVsInsertOrder(
    ConcurrentAppendTestCase, WithPostgres
):
    postgres_dcb_eventstore_class = PostgresDCBRecorderTS

    def test_commit_vs_insert_order(self) -> None:
        self._test_commit_vs_insert_order(self.eventstore)

    def test_fail_condition_is_effective(self) -> None:
        self._test_fail_condition_is_effective(self.eventstore)


class TestPostgresDCBRecorderTTCommitOrderVsInsertOrder(
    ConcurrentAppendTestCase, WithPostgres
):
    postgres_dcb_eventstore_class = PostgresDCBRecorderTT

    def test_commit_vs_insert_order(self) -> None:
        self._test_commit_vs_insert_order(self.eventstore)

    def test_fail_condition_is_effective(self) -> None:
        self._test_fail_condition_is_effective(self.eventstore)


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
        assert len(results) == 10

    benchmark(func)


@pytest.mark.benchmark(group="dcb-read-events-no-query-after-thousand-limit-ten")
def test_recorder_read_events_no_query_after_thousand_limit_ten(
    eventstore: DCBRecorder, benchmark: BenchmarkFixture
) -> None:
    events = generate_events(50000)
    eventstore.append(events)

    def func() -> None:
        results = eventstore.read(after=1000, limit=10)
        assert len(results) == 10

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
        assert len(results) == 1

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
        assert len(results) == 2

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
        assert len(results) == 2

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
        assert len(results) == 1

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
        assert len(results) == 2

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
        results = eventstore.read(query)
        assert len(results) == 0

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
