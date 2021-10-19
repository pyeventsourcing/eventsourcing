import asyncio
import time
from abc import ABC, abstractmethod
from uuid import uuid4

from eventsourcing.persistence import (
    AggregateRecorder,
    IntegrityError,
    StoredEvent,
)
from eventsourcing.tests.asyncio_testcase import IsolatedAsyncioTestCase


class AsyncAggregateRecorderTestCase(IsolatedAsyncioTestCase, ABC):
    @abstractmethod
    async def create_recorder(self) -> AggregateRecorder:
        pass

    async def test_insert_and_select(self):

        # Construct the recorder.
        recorder = await self.create_recorder()

        # Check we can call insert_events() with an empty list.
        await recorder.async_insert_events([])

        # Select stored events, expect empty list.
        originator_id1 = uuid4()
        self.assertEqual(
            await recorder.async_select_events(originator_id1, desc=True, limit=1),
            [],
        )

        # Write a stored event.
        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        await recorder.async_insert_events([stored_event1])

        # Select stored events, expect list of one.
        stored_events = await recorder.async_select_events(originator_id1)
        self.assertEqual(len(stored_events), 1)
        assert stored_events[0].originator_id == originator_id1
        assert stored_events[0].originator_version == 0
        assert stored_events[0].topic == "topic1"

        # Check get record conflict error if attempt to store it again.
        stored_events = await recorder.async_select_events(originator_id1)
        with self.assertRaises(IntegrityError):
            await recorder.async_insert_events([stored_event1])

        # Check writing of events is atomic.
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=1,
            topic="topic2",
            state=b"state2",
        )
        with self.assertRaises(IntegrityError):
            await recorder.async_insert_events([stored_event1, stored_event2])

        with self.assertRaises(IntegrityError):
            await recorder.async_insert_events([stored_event2, stored_event2])

        # Check still only have one record.
        stored_events = await recorder.async_select_events(originator_id1)
        self.assertEqual(len(stored_events), 1)
        assert stored_events[0].originator_id == originator_id1
        assert stored_events[0].originator_version == 0
        assert stored_events[0].topic == "topic1"

        # Check can write two events together.
        stored_event3 = StoredEvent(
            originator_id=originator_id1,
            originator_version=2,
            topic="topic3",
            state=b"state3",
        )
        await recorder.async_insert_events([stored_event2, stored_event3])

        # Check we got what was written.
        stored_events = await recorder.async_select_events(originator_id1)
        self.assertEqual(len(stored_events), 3)
        assert stored_events[0].originator_id == originator_id1
        assert stored_events[0].originator_version == 0
        assert stored_events[0].topic == "topic1"
        self.assertEqual(stored_events[0].state, b"state1")
        assert stored_events[1].originator_id == originator_id1
        assert stored_events[1].originator_version == 1
        assert stored_events[1].topic == "topic2"
        assert stored_events[1].state == b"state2"
        assert stored_events[2].originator_id == originator_id1
        assert stored_events[2].originator_version == 2
        assert stored_events[2].topic == "topic3"
        assert stored_events[2].state == b"state3"

        # Check we can get the last one recorded (used to get last snapshot).
        events = await recorder.async_select_events(originator_id1, desc=True, limit=1)
        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0],
            stored_event3,
        )

        # Check we can get the last one before a particular version.
        events = await recorder.async_select_events(
            originator_id1, lte=1, desc=True, limit=1
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0],
            stored_event2,
        )

        # Check we can get events between particular versions.
        events = await recorder.async_select_events(originator_id1, gt=0, lte=2)
        self.assertEqual(len(events), 2)
        self.assertEqual(
            events[0],
            stored_event2,
        )
        self.assertEqual(
            events[1],
            stored_event3,
        )

        # Check aggregate sequences are distinguished.
        originator_id2 = uuid4()
        self.assertEqual(
            await recorder.async_select_events(originator_id2),
            [],
        )

        # Write a stored event.
        stored_event4 = StoredEvent(
            originator_id=originator_id2,
            originator_version=0,
            topic="topic4",
            state=b"state4",
        )
        await recorder.async_insert_events([stored_event4])
        self.assertEqual(
            await recorder.async_select_events(originator_id2),
            [stored_event4],
        )

    async def test_performance(self):

        # Construct the recorder.
        recorder = await self.create_recorder()

        async def insert():
            originator_id = uuid4()

            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=0,
                topic="topic1",
                state=b"state1",
            )
            await recorder.async_insert_events([stored_event])

        # Warm up.
        for _ in range(20):
            await insert()

        number = 100
        started = time.time()

        for _ in range(number):
            await insert()

        duration = time.time() - started
        print(self, f"{duration / number:.9f}")

    async def test_performance_concurrent(self):

        # Construct the recorder.
        recorder = await self.create_recorder()

        async def insert():
            originator_id = uuid4()

            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=0,
                topic="topic1",
                state=b"state1",
            )
            await recorder.async_insert_events([stored_event])

        # Warm up.
        coroutines = [insert() for _ in range(20)]
        await asyncio.gather(*coroutines)

        number = 100
        started = time.time()

        coroutines = [insert() for _ in range(number)]
        await asyncio.gather(*coroutines)

        duration = time.time() - started
        print(self, f"{duration / number:.9f}")
