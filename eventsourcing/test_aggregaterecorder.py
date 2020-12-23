from abc import ABC, abstractmethod
from timeit import timeit
from unittest.case import TestCase
from uuid import uuid4

import psycopg2.errors
from psycopg2.errorcodes import UNDEFINED_TABLE

from eventsourcing.poporecorders import POPOAggregateRecorder
from eventsourcing.postgresrecorders import (
    PostgresAggregateRecorder,
    PostgresDatabase,
)
from eventsourcing.recorders import AggregateRecorder
from eventsourcing.sqliterecorders import (
    SQLiteDatabase,
    SQLiteAggregateRecorder,
)
from eventsourcing.storedevent import StoredEvent


class AggregateRecorderTestCase(TestCase, ABC):
    @abstractmethod
    def create_recorder(self) -> AggregateRecorder:
        pass

    def test_insert_and_select(self):

        # Construct the recorder.
        recorder = self.create_recorder()

        # Write two stored events.
        originator_id = uuid4()

        self.assertEqual(
            recorder.select_events(
                originator_id, desc=True, limit=1
            ),
            [],
        )

        stored_event1 = StoredEvent(
            originator_id=originator_id,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id,
            originator_version=1,
            topic="topic2",
            state=b"state2",
        )

        recorder.insert_events(
            [stored_event1, stored_event2]
        )

        stored_events = recorder.select_events(
            originator_id
        )

        # Check we got what was written.
        self.assertEqual(len(stored_events), 2)
        assert (
            stored_events[0].originator_id == originator_id
        )
        assert stored_events[0].originator_version == 0
        assert stored_events[0].topic == "topic1"
        self.assertEqual(stored_events[0].state, b"state1")
        assert (
            stored_events[1].originator_id == originator_id
        )
        assert stored_events[1].originator_version == 1
        assert stored_events[1].topic == "topic2"
        assert stored_events[1].state == b"state2"

        # Check recorded events are unique.
        stored_event3 = StoredEvent(
            originator_id=originator_id,
            originator_version=2,
            topic="topic3",
            state=b"state3",
        )

        try:
            recorder.insert_events(
                [stored_event2, stored_event3]
            )
        except AggregateRecorder.IntegrityError:
            pass
        else:
            self.fail("Integrity error not raised")

        # Check writing of events is atomic.
        stored_events = recorder.select_events(
            originator_id
        )
        assert len(stored_events) == 2, len(stored_events)

        # Check the third event can be written.
        recorder.insert_events([stored_event3])
        stored_events = recorder.select_events(
            originator_id
        )
        assert len(stored_events) == 3
        assert (
            stored_events[2].originator_id == originator_id
        )
        assert stored_events[2].originator_version == 2
        assert stored_events[2].topic == "topic3"
        assert stored_events[2].state == b"state3"

        events = recorder.select_events(
            originator_id, desc=True, limit=1
        )
        self.assertEqual(
            events[0],
            stored_event3,
        )

    def test_performance(self):

        # Construct the recorder.
        recorder = self.create_recorder()

        def insert():
            originator_id = uuid4()

            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=0,
                topic="topic1",
                state=b"state1",
            )
            recorder.insert_events([stored_event])

        # Warm up.
        number = 10
        timeit(insert, number=number)

        number = 100
        duration = timeit(insert, number=number)
        print(self, f"{duration / number:.9f}")


class TestPopoAggregateRecorder(AggregateRecorderTestCase):
    def create_recorder(self):
        return POPOAggregateRecorder()


class TestPostgresAggregateRecorder(AggregateRecorderTestCase):
    def setUp(self) -> None:
        recorder = PostgresAggregateRecorder()
        try:
            with recorder.db.transaction() as c:
                c.execute("DROP TABLE stored_events;")
        except psycopg2.errors.lookup(UNDEFINED_TABLE):
            pass

    def create_recorder(self):
        recorder = PostgresAggregateRecorder()
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()

    def test_insert_and_select(self):
        super().test_insert_and_select()


class TestSQLiteAggregateRecorder(AggregateRecorderTestCase):
    def create_recorder(self):
        recorder = SQLiteAggregateRecorder(
            SQLiteDatabase(":memory:")
        )
        recorder.create_table()
        return recorder


del AggregateRecorderTestCase
