from __future__ import annotations

import traceback
import zlib
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event, Thread, get_ident
from time import sleep
from timeit import timeit
from typing import TYPE_CHECKING, Any, Generic, cast
from unittest import TestCase
from uuid import UUID, uuid4

from typing_extensions import TypeVar

from eventsourcing.cipher import AESCipher
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.domain import DomainEvent, datetime_now_with_tzinfo
from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    DatetimeAsISO,
    DecimalAsStr,
    InfrastructureFactory,
    IntegrityError,
    JSONTranscoder,
    Mapper,
    Notification,
    ProcessRecorder,
    StoredEvent,
    Tracking,
    TrackingRecorder,
    Transcoder,
    Transcoding,
    UUIDAsHex,
    WaitInterruptedError,
)
from eventsourcing.utils import Environment, get_topic

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from typing_extensions import Never


class RecorderTestCase(TestCase, ABC):
    INITIAL_VERSION = 1

    def new_originator_id(self) -> UUID | str:
        return uuid4()


class AggregateRecorderTestCase(RecorderTestCase, ABC):
    @abstractmethod
    def create_recorder(self) -> AggregateRecorder:
        """"""

    def test_insert_and_select(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        # Check we can call insert_events() with an empty list.
        notification_ids = recorder.insert_events([])
        self.assertEqual(notification_ids, None)

        # Select stored events, expect empty list.
        originator_id1 = self.new_originator_id()
        self.assertEqual(
            recorder.select_events(originator_id1, desc=True, limit=1),
            [],
        )

        # Write a stored event.
        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION,
            topic="topic1",
            state=b"state1",
        )
        notification_ids = recorder.insert_events([stored_event1])
        self.assertEqual(notification_ids, None)

        # Select stored events, expect list of one.
        stored_events = recorder.select_events(originator_id1)
        self.assertEqual(len(stored_events), 1)
        self.assertEqual(stored_events[0].originator_id, originator_id1)
        self.assertEqual(stored_events[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(stored_events[0].topic, "topic1")
        self.assertEqual(stored_events[0].state, b"state1")
        self.assertIsInstance(stored_events[0].state, bytes)

        # Check get record conflict error if attempt to store it again.
        with self.assertRaises(IntegrityError):
            recorder.insert_events([stored_event1])

        # Check writing of events is atomic.
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 1,
            topic="topic2",
            state=b"state2",
        )
        with self.assertRaises(IntegrityError):
            recorder.insert_events([stored_event1, stored_event2])

        with self.assertRaises(IntegrityError):
            recorder.insert_events([stored_event2, stored_event2])

        # Check still only have one record.
        stored_events = recorder.select_events(originator_id1)
        self.assertEqual(len(stored_events), 1)
        self.assertEqual(stored_events[0].originator_id, stored_event1.originator_id)
        self.assertEqual(
            stored_events[0].originator_version, stored_event1.originator_version
        )
        self.assertEqual(stored_events[0].topic, stored_event1.topic)

        # Check can write two events together.
        stored_event3 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 2,
            topic="topic3",
            state=b"state3",
        )
        notification_ids = recorder.insert_events([stored_event2, stored_event3])
        self.assertEqual(notification_ids, None)

        # Check we got what was written.
        stored_events = recorder.select_events(originator_id1)
        self.assertEqual(len(stored_events), 3)
        self.assertEqual(stored_events[0].originator_id, originator_id1)
        self.assertEqual(stored_events[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(stored_events[0].topic, "topic1")
        self.assertEqual(stored_events[0].state, b"state1")
        self.assertEqual(stored_events[1].originator_id, originator_id1)
        self.assertEqual(stored_events[1].originator_version, self.INITIAL_VERSION + 1)
        self.assertEqual(stored_events[1].topic, "topic2")
        self.assertEqual(stored_events[1].state, b"state2")
        self.assertEqual(stored_events[2].originator_id, originator_id1)
        self.assertEqual(stored_events[2].originator_version, self.INITIAL_VERSION + 2)
        self.assertEqual(stored_events[2].topic, "topic3")
        self.assertEqual(stored_events[2].state, b"state3")

        # Check we can get the last one recorded (used to get last snapshot).
        stored_events = recorder.select_events(originator_id1, desc=True, limit=1)
        self.assertEqual(len(stored_events), 1)
        self.assertEqual(
            stored_events[0],
            stored_event3,
        )

        # Check we can get the last one before a particular version.
        stored_events = recorder.select_events(
            originator_id1, lte=self.INITIAL_VERSION + 1, desc=True, limit=1
        )
        self.assertEqual(len(stored_events), 1)
        self.assertEqual(
            stored_events[0],
            stored_event2,
        )

        # Check we can get events between versions (historical state with snapshot).
        stored_events = recorder.select_events(
            originator_id1, gt=self.INITIAL_VERSION, lte=self.INITIAL_VERSION + 1
        )
        self.assertEqual(len(stored_events), 1)
        self.assertEqual(
            stored_events[0],
            stored_event2,
        )

        # Check aggregate sequences are distinguished.
        originator_id2 = self.new_originator_id()
        self.assertEqual(
            recorder.select_events(originator_id2),
            [],
        )

        # Write a stored event in a different sequence.
        stored_event4 = StoredEvent(
            originator_id=originator_id2,
            originator_version=0,
            topic="topic4",
            state=b"state4",
        )
        recorder.insert_events([stored_event4])
        stored_events = recorder.select_events(originator_id2)
        self.assertEqual(
            stored_events,
            [stored_event4],
        )

    def test_performance(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        def insert() -> None:
            originator_id = self.new_originator_id()

            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=self.INITIAL_VERSION,
                topic="topic1",
                state=b"state1",
            )
            recorder.insert_events([stored_event])

        # Warm up.
        number = 10
        timeit(insert, number=number)

        number = 100
        duration = timeit(insert, number=number)
        print(
            self,
            f"\n{1000000 * duration / number:.1f} μs per insert, "
            f"{number / duration:.0f} inserts per second",
        )


_TApplicationRecorder = TypeVar(
    "_TApplicationRecorder", bound=ApplicationRecorder, default=ApplicationRecorder
)


class ApplicationRecorderTestCase(
    RecorderTestCase, ABC, Generic[_TApplicationRecorder]
):
    EXPECT_CONTIGUOUS_NOTIFICATION_IDS = True

    @abstractmethod
    def create_recorder(self) -> _TApplicationRecorder:
        """"""

    def test_insert_select(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        # Check notifications methods work when there aren't any.
        self.assertEqual(len(recorder.select_notifications(start=None, limit=3)), 0)
        self.assertEqual(
            len(recorder.select_notifications(start=None, limit=3, topics=["topic1"])),
            0,
        )

        self.assertIsNone(recorder.max_notification_id())

        # Write two stored events.
        originator_id1 = self.new_originator_id()
        originator_id2 = self.new_originator_id()

        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION,
            topic="topic1",
            state=b"state1",
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 1,
            topic="topic2",
            state=b"state2",
        )

        notification_ids = recorder.insert_events([stored_event1, stored_event2])
        self.assertEqual(notification_ids, [1, 2])

        # Store a third event.
        stored_event3 = StoredEvent(
            originator_id=originator_id2,
            originator_version=self.INITIAL_VERSION,
            topic="topic3",
            state=b"state3",
        )
        notification_ids = recorder.insert_events([stored_event3])
        self.assertEqual(notification_ids, [3])

        stored_events1 = recorder.select_events(originator_id1)
        stored_events2 = recorder.select_events(originator_id2)

        # Check we got what was written.
        self.assertEqual(len(stored_events1), 2)
        self.assertEqual(len(stored_events2), 1)

        # Check get record conflict error if attempt to store it again.
        with self.assertRaises(IntegrityError):
            recorder.insert_events([stored_event3])

        # sleep(1)  # Added to make eventsourcing-axon tests work.
        notifications = recorder.select_notifications(start=None, limit=10)
        self.assertEqual(len(notifications), 3)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].id, 2)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b"state2")
        self.assertEqual(notifications[2].id, 3)
        self.assertEqual(notifications[2].originator_id, originator_id2)
        self.assertEqual(notifications[2].topic, "topic3")
        self.assertEqual(notifications[2].state, b"state3")

        notifications = recorder.select_notifications(start=1, limit=10)
        self.assertEqual(len(notifications), 3)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].id, 2)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b"state2")
        self.assertEqual(notifications[2].id, 3)
        self.assertEqual(notifications[2].originator_id, originator_id2)
        self.assertEqual(notifications[2].topic, "topic3")
        self.assertEqual(notifications[2].state, b"state3")

        notifications = recorder.select_notifications(start=None, stop=2, limit=10)
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].id, 2)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b"state2")

        notifications = recorder.select_notifications(
            start=1, limit=10, inclusive_of_start=False
        )
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].id, 2)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic2")
        self.assertEqual(notifications[0].state, b"state2")
        self.assertEqual(notifications[1].id, 3)
        self.assertEqual(notifications[1].originator_id, originator_id2)
        self.assertEqual(notifications[1].topic, "topic3")
        self.assertEqual(notifications[1].state, b"state3")

        notifications = recorder.select_notifications(
            start=2, limit=10, inclusive_of_start=False
        )
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 3)
        self.assertEqual(notifications[0].originator_id, originator_id2)
        self.assertEqual(notifications[0].topic, "topic3")
        self.assertEqual(notifications[0].state, b"state3")

        notifications = recorder.select_notifications(
            start=None, limit=10, topics=["topic1", "topic2", "topic3"]
        )
        self.assertEqual(len(notifications), 3)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].id, 2)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b"state2")
        self.assertEqual(notifications[2].id, 3)
        self.assertEqual(notifications[2].originator_id, originator_id2)
        self.assertEqual(notifications[2].topic, "topic3")
        self.assertEqual(notifications[2].state, b"state3")

        notifications = recorder.select_notifications(1, 10, topics=["topic1"])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")

        notifications = recorder.select_notifications(1, 3, topics=["topic2"])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 2)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic2")
        self.assertEqual(notifications[0].state, b"state2")

        notifications = recorder.select_notifications(1, 3, topics=["topic3"])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 3)
        self.assertEqual(notifications[0].originator_id, originator_id2)
        self.assertEqual(notifications[0].topic, "topic3")
        self.assertEqual(notifications[0].state, b"state3")

        notifications = recorder.select_notifications(1, 3, topics=["topic1", "topic3"])
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].id, 3)
        self.assertEqual(notifications[1].topic, "topic3")
        self.assertEqual(notifications[1].state, b"state3")

        self.assertEqual(recorder.max_notification_id(), 3)

        # Check limit is working
        notifications = recorder.select_notifications(None, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 1)

        notifications = recorder.select_notifications(2, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 2)

        notifications = recorder.select_notifications(1, 1, inclusive_of_start=False)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 2)

        notifications = recorder.select_notifications(2, 2)
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].id, 2)
        self.assertEqual(notifications[1].id, 3)

        notifications = recorder.select_notifications(3, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 3)

        notifications = recorder.select_notifications(3, 1, inclusive_of_start=False)
        self.assertEqual(len(notifications), 0)

        notifications = recorder.select_notifications(start=2, limit=10, stop=2)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 2)

        notifications = recorder.select_notifications(start=1, limit=10, stop=2)
        self.assertEqual(len(notifications), 2, len(notifications))
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[1].id, 2)

        notifications = recorder.select_notifications(
            start=1, limit=10, stop=2, inclusive_of_start=False
        )
        self.assertEqual(len(notifications), 1, len(notifications))
        self.assertEqual(notifications[0].id, 2)

    def test_performance(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        def insert() -> None:
            originator_id = self.new_originator_id()

            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=self.INITIAL_VERSION,
                topic="topic1",
                state=b"state1",
            )
            recorder.insert_events([stored_event])

        # Warm up.
        number = 10
        timeit(insert, number=number)

        number = 100
        duration = timeit(insert, number=number)
        print(
            self,
            f"\n{1000000 * duration / number:.1f} μs per insert, "
            f"{number / duration:.0f} inserts per second",
        )

    def test_concurrent_no_conflicts(self, initial_position: int = 0) -> None:
        print(self)

        recorder = self.create_recorder()

        errors_happened = Event()
        errors: list[Exception] = []

        counts = {}
        threads: dict[int, int] = {}
        durations: dict[int, float] = {}

        num_writers = 10
        num_writes_per_writer = 100
        num_events_per_write = 100
        reader_sleep = 0.0001
        writer_sleep = 0.0001

        def insert_events() -> None:
            thread_id = get_ident()
            if thread_id not in threads:
                threads[thread_id] = len(threads)
            if thread_id not in counts:
                counts[thread_id] = 0
            if thread_id not in durations:
                durations[thread_id] = 0

            # thread_num = threads[thread_id]
            # count = counts[thread_id]

            originator_id = self.new_originator_id()
            stored_events = [
                StoredEvent(
                    originator_id=originator_id,
                    originator_version=i,
                    topic="topic",
                    state=b"state",
                )
                for i in range(num_events_per_write)
            ]
            started = datetime_now_with_tzinfo()
            # print(f"Thread {thread_num} write beginning #{count + 1}")
            try:
                recorder.insert_events(stored_events)

            except Exception as e:  # pragma: no cover
                if errors:
                    return
                ended = datetime_now_with_tzinfo()
                duration = (ended - started).total_seconds()
                print(f"Error after starting {duration}", e)
                errors.append(e)
            else:
                ended = datetime_now_with_tzinfo()
                duration = (ended - started).total_seconds()
                counts[thread_id] += 1
                durations[thread_id] = max(durations[thread_id], duration)
                sleep(writer_sleep)

        stop_reading = Event()

        def read_continuously() -> None:
            while not stop_reading.is_set():
                try:
                    recorder.select_notifications(
                        start=initial_position, limit=10, inclusive_of_start=False
                    )
                except Exception as e:  # pragma: no cover
                    errors.append(e)
                    return
                # else:
                sleep(reader_sleep)

        reader_thread1 = Thread(target=read_continuously)
        reader_thread1.start()

        reader_thread2 = Thread(target=read_continuously)
        reader_thread2.start()

        with ThreadPoolExecutor(max_workers=num_writers) as executor:
            futures = []
            for _ in range(num_writes_per_writer):
                if errors:  # pragma: no cover
                    break
                future = executor.submit(insert_events)
                futures.append(future)
            for future in futures:
                if errors:  # pragma: no cover
                    break
                try:
                    future.result()
                except Exception as e:  # pragma: no cover
                    errors.append(e)
                    break

        stop_reading.set()

        if errors:  # pragma: no cover
            raise errors[0]

        for thread_id, thread_num in threads.items():
            count = counts[thread_id]
            duration = durations[thread_id]
            print(f"Thread {thread_num} wrote {count} times (max dur {duration})")
        self.assertFalse(errors_happened.is_set())

    def test_concurrent_throughput(self) -> None:
        print(self)

        recorder = self.create_recorder()

        errors_happened = Event()

        # Match this to the batch page size in postgres insert for max throughput.
        num_events_per_job = 50
        num_jobs = 10
        num_workers = 4

        def insert_events() -> None:
            originator_id = self.new_originator_id()
            stored_events = [
                StoredEvent(
                    originator_id=originator_id,
                    originator_version=i,
                    topic="topic",
                    state=b"state",
                )
                for i in range(num_events_per_job)
            ]

            try:
                recorder.insert_events(stored_events)

            except Exception:  # pragma: no cover
                errors_happened.set()
                tb = traceback.format_exc()
                print(tb)

        # Warm up.
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for _ in range(num_workers):
                future = executor.submit(insert_events)
                futures.append(future)
            for future in futures:
                future.result()

        # Run.
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            started = datetime_now_with_tzinfo()
            futures = []
            for _ in range(num_jobs):
                future = executor.submit(insert_events)
                futures.append(future)
            for future in futures:
                future.result()

        self.assertFalse(errors_happened.is_set(), "There were errors (see above)")
        ended = datetime_now_with_tzinfo()
        rate = num_jobs * num_events_per_job / (ended - started).total_seconds()
        print(f"Rate: {rate:.0f} inserts per second")

    def optional_test_insert_subscribe(self, initial_position: int = 0) -> None:

        recorder = self.create_recorder()

        # Get the max notification ID.
        max_notification_id1 = recorder.max_notification_id()

        # Write two stored events.
        originator_id1 = self.new_originator_id()
        originator_id2 = self.new_originator_id()

        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION,
            topic="topic1",
            state=b"state1",
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 1,
            topic="topic2",
            state=b"state2",
        )

        notification_ids = recorder.insert_events([stored_event1, stored_event2])
        if self.EXPECT_CONTIGUOUS_NOTIFICATION_IDS:
            self.assertEqual(
                notification_ids, [1 + initial_position, 2 + initial_position]
            )

        # Get the max notification ID.
        max_notification_id2 = recorder.max_notification_id()

        # Start a subscription with default value for 'start'.
        with recorder.subscribe(gt=initial_position) as subscription:

            # Receive events from the subscription.
            for _ in subscription:
                break

        # Start a subscription with None value for 'start'.
        with recorder.subscribe(gt=initial_position) as subscription:

            # Receive events from the subscription.
            for _ in subscription:
                break

        # Start a subscription with int value for 'start'.
        with recorder.subscribe(gt=max_notification_id1) as subscription:

            # Receive events from the subscription.
            notifications: list[Notification] = []
            for notification in subscription:
                notifications.append(notification)
                if len(notifications) == 2:
                    break

            # Check the events we received are the ones that were written.
            self.assertEqual(
                stored_event1.originator_id, notifications[0].originator_id
            )
            self.assertEqual(
                stored_event1.originator_version, notifications[0].originator_version
            )
            self.assertEqual(
                stored_event2.originator_id, notifications[1].originator_id
            )
            self.assertEqual(
                stored_event2.originator_version, notifications[1].originator_version
            )
            if self.EXPECT_CONTIGUOUS_NOTIFICATION_IDS:
                self.assertEqual(1 + initial_position, notifications[0].id)
                self.assertEqual(2 + initial_position, notifications[1].id)

            # Store a third event.
            stored_event3 = StoredEvent(
                originator_id=originator_id2,
                originator_version=self.INITIAL_VERSION,
                topic="topic3",
                state=b"state3",
            )
            notification_ids = recorder.insert_events([stored_event3])
            if self.EXPECT_CONTIGUOUS_NOTIFICATION_IDS:
                self.assertEqual(notification_ids, [3 + initial_position])

            # Receive events from the subscription.
            for notification in subscription:
                notifications.append(notification)
                if len(notifications) == 3:
                    break

            # Check the events we received are the ones that were written.
            self.assertEqual(
                stored_event3.originator_id, notifications[2].originator_id
            )
            self.assertEqual(
                stored_event3.originator_version, notifications[2].originator_version
            )
            if self.EXPECT_CONTIGUOUS_NOTIFICATION_IDS:
                self.assertEqual(3 + initial_position, notifications[2].id)

        # Start a subscription with int value for 'start'.
        with recorder.subscribe(gt=max_notification_id2) as subscription:

            # Receive events from the subscription.
            notifications = []
            for notification in subscription:
                notifications.append(notification)
                if len(notifications) == 1:
                    break

            # Check the events we received are the ones that were written.
            self.assertEqual(
                stored_event3.originator_id, notifications[0].originator_id
            )

        # Start a subscription, call stop() during iteration.
        with recorder.subscribe(gt=initial_position) as subscription:

            # Receive events from the subscription.
            for i, _ in enumerate(subscription):
                subscription.stop()
                # Shouldn't get here twice...
                self.assertLess(i, 1, "Got here twice")

        # Start a subscription, call stop() before iteration.
        subscription = recorder.subscribe(gt=None)
        with subscription:
            subscription.stop()
            # Receive events from the subscription.
            for _ in subscription:
                # Shouldn't get here...
                self.fail("Got here")

        # Start a subscription, call stop() before entering context manager.
        subscription = recorder.subscribe(gt=None)
        subscription.stop()
        with subscription:
            # Receive events from the subscription.
            for _ in subscription:
                # Shouldn't get here...
                self.fail("Got here")

        # Start a subscription with topics.
        subscription = recorder.subscribe(gt=None, topics=["topic3"])
        with subscription:
            for notification in subscription:
                self.assertEqual(notification.topic, "topic3")
                if (
                    notification.originator_id == stored_event3.originator_id
                    and notification.originator_version
                    == stored_event3.originator_version
                ):
                    break

    def close_db_connection(self, *args: Any) -> None:
        """"""


class TrackingRecorderTestCase(TestCase, ABC):
    @abstractmethod
    def create_recorder(self) -> TrackingRecorder:
        """"""

    def test_insert_tracking(self) -> None:
        tracking_recorder = self.create_recorder()

        # Construct tracking objects.
        tracking1 = Tracking("upstream1", 21)
        tracking2 = Tracking("upstream1", 22)
        tracking3 = Tracking("upstream2", 21)

        # Insert tracking objects.
        tracking_recorder.insert_tracking(tracking=tracking1)
        tracking_recorder.insert_tracking(tracking=tracking2)
        tracking_recorder.insert_tracking(tracking=tracking3)

        # raise Exception(tracking_recorder.max_tracking_id(tracking1.application_name))

        # Fail to insert same tracking object twice.
        with self.assertRaises(IntegrityError):
            tracking_recorder.insert_tracking(tracking=tracking1)
        with self.assertRaises(IntegrityError):
            tracking_recorder.insert_tracking(tracking=tracking2)
        with self.assertRaises(IntegrityError):
            tracking_recorder.insert_tracking(tracking=tracking3)

        # Get max tracking ID.
        self.assertEqual(tracking_recorder.max_tracking_id("upstream1"), 22)
        self.assertEqual(tracking_recorder.max_tracking_id("upstream2"), 21)
        self.assertIsNone(tracking_recorder.max_tracking_id("upstream3"))

        # Check if an event notification has been processed.
        self.assertTrue(tracking_recorder.has_tracking_id("upstream1", None))
        self.assertTrue(tracking_recorder.has_tracking_id("upstream1", 20))
        self.assertTrue(tracking_recorder.has_tracking_id("upstream1", 21))
        self.assertTrue(tracking_recorder.has_tracking_id("upstream1", 22))
        self.assertFalse(tracking_recorder.has_tracking_id("upstream1", 23))

        self.assertTrue(tracking_recorder.has_tracking_id("upstream2", None))
        self.assertTrue(tracking_recorder.has_tracking_id("upstream2", 20))
        self.assertTrue(tracking_recorder.has_tracking_id("upstream2", 21))
        self.assertFalse(tracking_recorder.has_tracking_id("upstream2", 22))

        self.assertTrue(tracking_recorder.has_tracking_id("upstream2", None))
        self.assertFalse(tracking_recorder.has_tracking_id("upstream2", 22))

        # Construct more tracking objects.
        tracking4 = Tracking("upstream1", 23)
        tracking5 = Tracking("upstream1", 24)

        tracking_recorder.insert_tracking(tracking5)

        # Can't fill in the gap.
        with self.assertRaises(IntegrityError):
            tracking_recorder.insert_tracking(tracking4)

        self.assertTrue(tracking_recorder.has_tracking_id("upstream1", 23))

    def test_wait(self) -> None:
        tracking_recorder = self.create_recorder()

        tracking_recorder.wait("upstream1", None)

        with self.assertRaises(TimeoutError):
            tracking_recorder.wait("upstream1", 21, timeout=0.1)

        tracking1 = Tracking(notification_id=21, application_name="upstream1")
        tracking_recorder.insert_tracking(tracking=tracking1)
        tracking_recorder.wait("upstream1", None)
        tracking_recorder.wait("upstream1", 10)
        tracking_recorder.wait("upstream1", 21)
        with self.assertRaises(TimeoutError):
            tracking_recorder.wait("upstream1", 22, timeout=0.1)
        with self.assertRaises(WaitInterruptedError):
            interrupt = Event()
            interrupt.set()
            tracking_recorder.wait("upstream1", 22, interrupt=interrupt)


class ProcessRecorderTestCase(RecorderTestCase, ABC):
    @abstractmethod
    def create_recorder(self) -> ProcessRecorder:
        """"""

    def test_insert_select(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        # Get current position.
        self.assertIsNone(recorder.max_tracking_id("upstream_app"))

        # Write two stored events.
        originator_id1 = self.new_originator_id()
        originator_id2 = self.new_originator_id()

        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=1,
            topic="topic1",
            state=b"state1",
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=2,
            topic="topic2",
            state=b"state2",
        )
        stored_event3 = StoredEvent(
            originator_id=originator_id2,
            originator_version=1,
            topic="topic3",
            state=b"state3",
        )
        stored_event4 = StoredEvent(
            originator_id=originator_id2,
            originator_version=2,
            topic="topic4",
            state=b"state4",
        )
        tracking1 = Tracking(
            application_name="upstream_app",
            notification_id=1,
        )
        tracking2 = Tracking(
            application_name="upstream_app",
            notification_id=2,
        )

        # Insert two events with tracking info.
        recorder.insert_events(
            stored_events=[
                stored_event1,
                stored_event2,
            ],
            tracking=tracking1,
        )

        # Check get record conflict error if attempt to store same event again.
        with self.assertRaises(IntegrityError):
            recorder.insert_events(
                stored_events=[stored_event2],
                tracking=tracking2,
            )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            1,
        )

        # Check can't insert third event with same tracking info.
        with self.assertRaises(IntegrityError):
            recorder.insert_events(
                stored_events=[stored_event3],
                tracking=tracking1,
            )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            1,
        )

        # Insert third event with different tracking info.
        recorder.insert_events(
            stored_events=[stored_event3],
            tracking=tracking2,
        )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            2,
        )

        # Insert fourth event without tracking info.
        recorder.insert_events(
            stored_events=[stored_event4],
        )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            2,
        )

    def test_has_tracking_id(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        self.assertTrue(recorder.has_tracking_id("upstream_app", None))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 1))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 2))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 3))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 4))

        tracking1 = Tracking(
            application_name="upstream_app",
            notification_id=1,
        )
        tracking3 = Tracking(
            application_name="upstream_app",
            notification_id=3,
        )

        recorder.insert_events(
            stored_events=[],
            tracking=tracking1,
        )

        self.assertTrue(recorder.has_tracking_id("upstream_app", 1))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 2))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 3))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 4))

        recorder.insert_events(
            stored_events=[],
            tracking=tracking3,
        )

        self.assertTrue(recorder.has_tracking_id("upstream_app", 1))
        self.assertTrue(recorder.has_tracking_id("upstream_app", 2))
        self.assertTrue(recorder.has_tracking_id("upstream_app", 3))
        self.assertFalse(recorder.has_tracking_id("upstream_app", 4))

    def test_raises_when_lower_inserted_later(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        tracking1 = Tracking(
            application_name="upstream_app",
            notification_id=1,
        )
        tracking2 = Tracking(
            application_name="upstream_app",
            notification_id=2,
        )

        # Insert tracking info.
        recorder.insert_events(
            stored_events=[],
            tracking=tracking2,
        )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            2,
        )

        # Insert tracking info.
        with self.assertRaises(IntegrityError):
            recorder.insert_events(
                stored_events=[],
                tracking=tracking1,
            )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            2,
        )

    def test_performance(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        number = 100

        notification_ids = iter(range(1, number + 1))

        def insert_events() -> None:
            originator_id = self.new_originator_id()

            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=0,
                topic="topic1",
                state=b"state1",
            )
            tracking1 = Tracking(
                application_name="upstream_app",
                notification_id=next(notification_ids),
            )

            recorder.insert_events(
                stored_events=[
                    stored_event,
                ],
                tracking=tracking1,
            )

        duration = timeit(insert_events, number=number)
        print(
            f"\n{self}",
            f"{1000000 * duration / number:.1f} μs per insert, "
            f"{number / duration:.0f} inserts per second",
        )


class NonInterleavingNotificationIDsBaseCase(RecorderTestCase, ABC):
    insert_num = 1000

    def test(self) -> None:
        recorder = self.create_recorder()

        max_notification_id = recorder.max_notification_id()

        race_started = Event()

        originator1_id = self.new_originator_id()
        originator2_id = self.new_originator_id()

        stack1 = self.create_stack(originator1_id)
        stack2 = self.create_stack(originator2_id)

        errors = []

        def insert_stack(stack: Sequence[StoredEvent]) -> None:
            try:
                race_started.wait()
                recorder.insert_events(stack)
            except Exception as e:
                errors.append(e)

        thread1 = Thread(target=insert_stack, args=(stack1,), daemon=True)
        thread2 = Thread(target=insert_stack, args=(stack2,), daemon=True)

        thread1.start()
        thread2.start()

        race_started.set()

        thread1.join()
        thread2.join()

        if errors:
            raise errors[0]

        # sleep(1)  # Added to make eventsourcing-axon tests work.
        notifications = recorder.select_notifications(
            start=max_notification_id,
            limit=2 * self.insert_num,
            inclusive_of_start=False,
        )
        ids_for_sequence1 = [
            e.id for e in notifications if e.originator_id == originator1_id
        ]
        ids_for_sequence2 = [
            e.id for e in notifications if e.originator_id == originator2_id
        ]
        self.assertEqual(self.insert_num, len(ids_for_sequence1))
        self.assertEqual(self.insert_num, len(ids_for_sequence2))

        max_id_for_sequence1 = max(ids_for_sequence1)
        max_id_for_sequence2 = max(ids_for_sequence2)
        min_id_for_sequence1 = min(ids_for_sequence1)
        min_id_for_sequence2 = min(ids_for_sequence2)

        if max_id_for_sequence1 > min_id_for_sequence2:
            self.assertGreater(min_id_for_sequence1, max_id_for_sequence2)
        else:
            self.assertGreater(min_id_for_sequence2, max_id_for_sequence1)

    def create_stack(self, originator_id: UUID | str) -> Sequence[StoredEvent]:
        return [
            StoredEvent(
                originator_id=originator_id,
                originator_version=i,
                topic="non-interleaving-test-event",
                state=b"{}",
            )
            for i in range(self.insert_num)
        ]

    @abstractmethod
    def create_recorder(self) -> ApplicationRecorder:
        pass


_TInfrastrutureFactory = TypeVar(
    "_TInfrastrutureFactory", bound=InfrastructureFactory[Any]
)


class InfrastructureFactoryTestCase(ABC, TestCase, Generic[_TInfrastrutureFactory]):
    env: Environment

    @abstractmethod
    def expected_factory_class(self) -> type[_TInfrastrutureFactory]:
        pass

    @abstractmethod
    def expected_aggregate_recorder_class(self) -> type[AggregateRecorder]:
        pass

    @abstractmethod
    def expected_application_recorder_class(self) -> type[ApplicationRecorder]:
        pass

    @abstractmethod
    def expected_tracking_recorder_class(self) -> type[TrackingRecorder]:
        pass

    @abstractmethod
    def tracking_recorder_subclass(self) -> type[TrackingRecorder]:
        pass

    @abstractmethod
    def expected_process_recorder_class(self) -> type[ProcessRecorder]:
        pass

    def setUp(self) -> None:
        self.factory = cast(
            _TInfrastrutureFactory, InfrastructureFactory.construct(self.env)
        )
        self.assertIsInstance(self.factory, self.expected_factory_class())
        self.transcoder = JSONTranscoder()
        self.transcoder.register(UUIDAsHex())
        self.transcoder.register(DecimalAsStr())
        self.transcoder.register(DatetimeAsISO())

    def tearDown(self) -> None:
        self.factory.close()

    def test_mapper(self) -> None:
        # Want to construct:
        #  - application recorder
        #  - snapshot recorder
        #  - mapper
        #  - event store
        #  - snapshot store

        # Want to make configurable:
        #  - cipher (and cipher key)
        #  - compressor
        #  - application recorder class (and db uri, and session)
        #  - snapshot recorder class (and db uri, and session)

        # Common environment:
        #  - factory topic
        #  - cipher topic
        #  - cipher key
        #  - compressor topic

        # POPO environment:

        # SQLite environment:
        #  - database topic
        #  - table name for stored events
        #  - table name for snapshots

        # Create mapper.

        mapper: Mapper[UUID] = self.factory.mapper(
            transcoder=self.transcoder,
        )
        self.assertIsInstance(mapper, Mapper)
        self.assertIsNone(mapper.cipher)
        self.assertIsNone(mapper.compressor)

    def test_mapper_with_compressor(self) -> None:
        # Create mapper with compressor class as topic.
        self.env[self.factory.COMPRESSOR_TOPIC] = get_topic(ZlibCompressor)
        mapper: Mapper[UUID] = self.factory.mapper(transcoder=self.transcoder)
        self.assertIsInstance(mapper, Mapper)
        self.assertIsInstance(mapper.compressor, ZlibCompressor)
        self.assertIsNone(mapper.cipher)

        # Create mapper with compressor module as topic.
        self.env[self.factory.COMPRESSOR_TOPIC] = "zlib"
        mapper = self.factory.mapper(transcoder=self.transcoder)
        self.assertIsInstance(mapper, Mapper)
        self.assertEqual(mapper.compressor, zlib)
        self.assertIsNone(mapper.cipher)

    def test_mapper_with_cipher(self) -> None:
        # Check cipher needs a key.
        self.env[self.factory.CIPHER_TOPIC] = get_topic(AESCipher)

        with self.assertRaises(EnvironmentError):
            self.factory.mapper(transcoder=self.transcoder)

        # Check setting key but no topic defers to AES.
        del self.env[self.factory.CIPHER_TOPIC]

        cipher_key = AESCipher.create_key(16)
        self.env[AESCipher.CIPHER_KEY] = cipher_key

        # Create mapper with cipher.
        mapper: Mapper[UUID] = self.factory.mapper(transcoder=self.transcoder)
        self.assertIsInstance(mapper, Mapper)
        self.assertIsNotNone(mapper.cipher)
        self.assertIsNone(mapper.compressor)

    def test_mapper_with_cipher_and_compressor(
        self,
    ) -> None:
        # Create mapper with cipher and compressor.
        self.env[self.factory.COMPRESSOR_TOPIC] = get_topic(ZlibCompressor)

        self.env[self.factory.CIPHER_TOPIC] = get_topic(AESCipher)
        cipher_key = AESCipher.create_key(16)
        self.env[AESCipher.CIPHER_KEY] = cipher_key

        mapper: Mapper[UUID] = self.factory.mapper(transcoder=self.transcoder)
        self.assertIsInstance(mapper, Mapper)
        self.assertIsNotNone(mapper.cipher)
        self.assertIsNotNone(mapper.compressor)

    def test_mapper_with_wrong_cipher_key(self) -> None:
        self.env.name = "App1"
        self.env[self.factory.CIPHER_TOPIC] = get_topic(AESCipher)
        cipher_key1 = AESCipher.create_key(16)
        cipher_key2 = AESCipher.create_key(16)
        self.env["APP1_" + AESCipher.CIPHER_KEY] = cipher_key1
        self.env["APP2_" + AESCipher.CIPHER_KEY] = cipher_key2

        mapper1: Mapper[UUID] = self.factory.mapper(
            transcoder=self.transcoder,
        )

        domain_event = DomainEvent(
            originator_id=uuid4(),
            originator_version=1,
            timestamp=DomainEvent.create_timestamp(),
        )
        stored_event = mapper1.to_stored_event(domain_event)
        copy = mapper1.to_domain_event(stored_event)
        self.assertEqual(domain_event.originator_id, copy.originator_id)

        self.env.name = "App2"
        mapper2: Mapper[UUID] = self.factory.mapper(
            transcoder=self.transcoder,
        )
        # This should fail because the infrastructure factory
        # should read different cipher keys from the environment.
        with self.assertRaises(ValueError):
            mapper2.to_domain_event(stored_event)

    def test_create_aggregate_recorder(self) -> None:
        recorder = self.factory.aggregate_recorder()
        self.assertEqual(type(recorder), self.expected_aggregate_recorder_class())

        self.assertIsInstance(recorder, AggregateRecorder)

        # Exercise code path where table is not created.
        self.env["CREATE_TABLE"] = "f"
        recorder = self.factory.aggregate_recorder()
        self.assertEqual(type(recorder), self.expected_aggregate_recorder_class())

    def test_create_application_recorder(self) -> None:
        recorder = self.factory.application_recorder()
        self.assertEqual(type(recorder), self.expected_application_recorder_class())
        self.assertIsInstance(recorder, ApplicationRecorder)

        # Exercise code path where table is not created.
        self.env["CREATE_TABLE"] = "f"
        recorder = self.factory.application_recorder()
        self.assertEqual(type(recorder), self.expected_application_recorder_class())

    def test_create_tracking_recorder(self) -> None:
        recorder = self.factory.tracking_recorder()
        self.assertEqual(type(recorder), self.expected_tracking_recorder_class())
        self.assertIsInstance(recorder, TrackingRecorder)

        # Exercise code path where table is not created.
        self.env["CREATE_TABLE"] = "f"
        recorder = self.factory.tracking_recorder()
        self.assertEqual(type(recorder), self.expected_tracking_recorder_class())

        # Exercise code path where tracking recorder class is specified as arg.
        subclass = self.tracking_recorder_subclass()
        recorder = self.factory.tracking_recorder(subclass)
        self.assertEqual(type(recorder), subclass)

        # Exercise code path where tracking recorder class is specified as topic.
        self.factory.env[self.factory.TRACKING_RECORDER_TOPIC] = get_topic(subclass)
        recorder = self.factory.tracking_recorder()
        self.assertEqual(type(recorder), subclass)

    def test_create_process_recorder(self) -> None:
        recorder = self.factory.process_recorder()
        self.assertEqual(type(recorder), self.expected_process_recorder_class())
        self.assertIsInstance(recorder, ProcessRecorder)

        # Exercise code path where table is not created.
        self.env["CREATE_TABLE"] = "f"
        recorder = self.factory.process_recorder()
        self.assertEqual(type(recorder), self.expected_process_recorder_class())


def tmpfile_uris() -> Iterator[str]:
    tmp_files = []
    ram_disk_path = Path("/Volumes/RAM DISK/")
    prefix: str | None = None
    if ram_disk_path.exists():
        prefix = str(ram_disk_path)
    while True:
        with NamedTemporaryFile(
            prefix=prefix,
            suffix="_eventsourcing_test.db",
        ) as tmp_file:
            tmp_files.append(tmp_file)
            yield "file:" + tmp_file.name


class CustomType1:
    def __init__(self, value: UUID):
        self.value = value

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        raise NotImplementedError


class CustomType2:
    def __init__(self, value: CustomType1):
        self.value = value

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        raise NotImplementedError


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class Mydict(dict[_KT, _VT]):  # noqa: PLW1641
    def __repr__(self) -> str:
        return f"{type(self).__name__}({super().__repr__()})"

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and super().__eq__(other)


_T = TypeVar("_T")


class MyList(list[_T]):  # noqa: PLW1641
    def __repr__(self) -> str:
        return f"{type(self).__name__}({super().__repr__()})"

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and super().__eq__(other)


class MyStr(str):
    __slots__ = ()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({super().__repr__()})"

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and super().__eq__(other)

    def __hash__(self) -> int:
        return hash(str(self))


class MyInt(int):
    def __repr__(self) -> str:
        return f"{type(self).__name__}({super().__repr__()})"

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and super().__eq__(other)

    def __hash__(self) -> int:
        return int(self)


class MyClass:
    pass


class CustomType1AsDict(Transcoding):
    type = CustomType1
    name = "custom_type1_as_dict"

    def encode(self, obj: CustomType1) -> UUID:
        return obj.value

    def decode(self, data: UUID) -> CustomType1:
        assert isinstance(data, UUID)
        return CustomType1(value=data)


class CustomType2AsDict(Transcoding):
    type = CustomType2
    name = "custom_type2_as_dict"

    def encode(self, obj: CustomType2) -> CustomType1:
        return obj.value

    def decode(self, data: CustomType1) -> CustomType2:
        assert isinstance(data, CustomType1)
        return CustomType2(data)


class TranscoderTestCase(TestCase):
    def setUp(self) -> None:
        self.transcoder = self.construct_transcoder()

    def construct_transcoder(self) -> Transcoder:
        raise NotImplementedError

    def test_str(self) -> None:
        obj = "a"
        data = self.transcoder.encode(obj)
        self.assertEqual(data, b'"a"')
        self.assertEqual(obj, self.transcoder.decode(data))

        obj = "abc"
        data = self.transcoder.encode(obj)
        self.assertEqual(data, b'"abc"')
        self.assertEqual(obj, self.transcoder.decode(data))

        obj = "a'b"
        data = self.transcoder.encode(obj)
        self.assertEqual(data, b'''"a'b"''')
        self.assertEqual(obj, self.transcoder.decode(data))

        obj = 'a"b'
        data = self.transcoder.encode(obj)
        self.assertEqual(data, b'''"a\\"b"''')
        self.assertEqual(obj, self.transcoder.decode(data))

        obj = "🐈 哈哈"
        data = self.transcoder.encode(obj)
        self.assertEqual(b'"\xf0\x9f\x90\x88 \xe5\x93\x88\xe5\x93\x88"', data)
        self.assertEqual(obj, self.transcoder.decode(data))

        # Check data encoded with ensure_ascii=True can be decoded okay.
        legacy_encoding_with_ensure_ascii_true = b'"\\ud83d\\udc08 \\u54c8\\u54c8"'
        self.assertEqual(
            obj, self.transcoder.decode(legacy_encoding_with_ensure_ascii_true)
        )

    def test_dict(self) -> None:
        # Empty dict.
        obj1: dict[Never, Never] = {}
        data = self.transcoder.encode(obj1)
        self.assertEqual(data, b"{}")
        self.assertEqual(obj1, self.transcoder.decode(data))

        # dict with single key.
        obj2 = {"a": 1}
        data = self.transcoder.encode(obj2)
        self.assertEqual(data, b'{"a":1}')
        self.assertEqual(obj2, self.transcoder.decode(data))

        # dict with many keys.
        obj3 = {"a": 1, "b": 2}
        data = self.transcoder.encode(obj3)
        self.assertEqual(data, b'{"a":1,"b":2}')
        self.assertEqual(obj3, self.transcoder.decode(data))

        # Empty dict in dict.
        obj4: dict[str, dict[Never, Never]] = {"a": {}}
        data = self.transcoder.encode(obj4)
        self.assertEqual(data, b'{"a":{}}')
        self.assertEqual(obj4, self.transcoder.decode(data))

        # Empty dicts in dict.
        obj5: dict[str, dict[Never, Never]] = {"a": {}, "b": {}}
        data = self.transcoder.encode(obj5)
        self.assertEqual(data, b'{"a":{},"b":{}}')
        self.assertEqual(obj5, self.transcoder.decode(data))

        # Empty dict in dict in dict.
        obj6: dict[str, dict[str, dict[Never, Never]]] = {"a": {"b": {}}}
        data = self.transcoder.encode(obj6)
        self.assertEqual(data, b'{"a":{"b":{}}}')
        self.assertEqual(obj6, self.transcoder.decode(data))

        # Int in dict in dict in dict.
        obj7 = {"a": {"b": {"c": 1}}}
        data = self.transcoder.encode(obj7)
        self.assertEqual(data, b'{"a":{"b":{"c":1}}}')
        self.assertEqual(obj7, self.transcoder.decode(data))

        # TODO: Int keys?
        # obj = {1: "a"}
        # data = self.transcoder.encode(obj)
        # self.assertEqual(data, b'{1:{"a"}')
        # self.assertEqual(obj, self.transcoder.decode(data))

    def test_dict_with_len_2_and__data_(self) -> None:
        obj = {"_data_": 1, "something_else": 2}
        data = self.transcoder.encode(obj)
        self.assertEqual(obj, self.transcoder.decode(data))

    def test_dict_with_len_2_and__type_(self) -> None:
        obj = {"_type_": 1, "something_else": 2}
        data = self.transcoder.encode(obj)
        self.assertEqual(obj, self.transcoder.decode(data))

    def test_dict_subclass(self) -> None:
        my_dict = Mydict({"a": 1})
        data = self.transcoder.encode(my_dict)
        self.assertEqual(b'{"_type_":"mydict","_data_":{"a":1}}', data)
        copy = self.transcoder.decode(data)
        self.assertEqual(my_dict, copy)

    def test_list_subclass(self) -> None:
        my_list = MyList((("a", 1),))
        data = self.transcoder.encode(my_list)
        copy = self.transcoder.decode(data)
        self.assertEqual(my_list, copy)

    def test_str_subclass(self) -> None:
        my_str = MyStr("a")
        data = self.transcoder.encode(my_str)
        copy = self.transcoder.decode(data)
        self.assertEqual(my_str, copy)

    def test_int_subclass(self) -> None:
        my_int = MyInt(3)
        data = self.transcoder.encode(my_int)
        copy = self.transcoder.decode(data)
        self.assertEqual(my_int, copy)

    def test_tuple(self) -> None:
        # Empty tuple.
        obj1 = ()
        data = self.transcoder.encode(obj1)
        self.assertEqual(data, b'{"_type_":"tuple_as_list","_data_":[]}')
        self.assertEqual(obj1, self.transcoder.decode(data))

        # Empty tuple in a tuple.
        obj2 = ((),)
        data = self.transcoder.encode(obj2)
        self.assertEqual(obj2, self.transcoder.decode(data))

        # Int in tuple in a tuple.
        obj3 = ((1, 2),)
        data = self.transcoder.encode(obj3)
        self.assertEqual(obj3, self.transcoder.decode(data))

        # Str in tuple in a tuple.
        obj4 = (("a", "b"),)
        data = self.transcoder.encode(obj4)
        self.assertEqual(obj4, self.transcoder.decode(data))

        # Int and str in tuple in a tuple.
        obj5 = ((1, "a"),)
        data = self.transcoder.encode(obj5)
        self.assertEqual(obj5, self.transcoder.decode(data))

    def test_list(self) -> None:
        # Empty list.
        obj1: list[Never] = []
        data = self.transcoder.encode(obj1)
        self.assertEqual(obj1, self.transcoder.decode(data))

        # Empty list in a list.
        obj2: list[list[Never]] = [[]]
        data = self.transcoder.encode(obj2)
        self.assertEqual(obj2, self.transcoder.decode(data))

        # Int in list in a list.
        obj3 = [[1, 2]]
        data = self.transcoder.encode(obj3)
        self.assertEqual(obj3, self.transcoder.decode(data))

        # Str in list in a list.
        obj4 = [["a", "b"]]
        data = self.transcoder.encode(obj4)
        self.assertEqual(obj4, self.transcoder.decode(data))

        # Int and str in list in a list.
        obj5 = [[1, "a"]]
        data = self.transcoder.encode(obj5)
        self.assertEqual(obj5, self.transcoder.decode(data))

    def test_mixed(self) -> None:
        obj1 = [(1, "a"), {"b": 2}]
        data = self.transcoder.encode(obj1)
        self.assertEqual(obj1, self.transcoder.decode(data))

        obj2 = ([1, "a"], {"b": 2})
        data = self.transcoder.encode(obj2)
        self.assertEqual(obj2, self.transcoder.decode(data))

        obj3 = {"a": (1, 2), "b": [3, 4]}
        data = self.transcoder.encode(obj3)
        self.assertEqual(obj3, self.transcoder.decode(data))

    def test_custom_type_in_dict(self) -> None:
        # Int in dict in dict in dict.
        obj = {"a": CustomType2(CustomType1(UUID("b2723fe2c01a40d2875ea3aac6a09ff5")))}
        data = self.transcoder.encode(obj)
        decoded_obj = self.transcoder.decode(data)
        self.assertEqual(obj, decoded_obj)

    def test_nested_custom_type(self) -> None:
        obj = CustomType2(CustomType1(UUID("b2723fe2c01a40d2875ea3aac6a09ff5")))
        data = self.transcoder.encode(obj)
        expect = (
            b'{"_type_":"custom_type2_as_dict","_data_":'
            b'{"_type_":"custom_type1_as_dict","_data_":'
            b'{"_type_":"uuid_hex","_data_":"b2723fe2c01'
            b'a40d2875ea3aac6a09ff5"}}}'
        )
        self.assertEqual(data, expect)
        copy = self.transcoder.decode(data)
        self.assertIsInstance(copy, CustomType2)
        self.assertIsInstance(copy.value, CustomType1)
        self.assertIsInstance(copy.value.value, UUID)
        self.assertEqual(copy.value.value, obj.value.value)

    def test_custom_type_error(self) -> None:
        # Expect a TypeError when encoding because transcoding not registered.
        with self.assertRaises(TypeError) as cm:
            self.transcoder.encode(MyClass())

        self.assertEqual(
            cm.exception.args[0],
            "Object of type <class 'eventsourcing.tests.persistence."
            "MyClass'> is not serializable. Please define "
            "and register a custom transcoding for this type.",
        )

        # Expect a TypeError when encoding because transcoding not registered (nested).
        with self.assertRaises(TypeError) as cm:
            self.transcoder.encode({"a": MyClass()})

        self.assertEqual(
            cm.exception.args[0],
            "Object of type <class 'eventsourcing.tests.persistence."
            "MyClass'> is not serializable. Please define "
            "and register a custom transcoding for this type.",
        )

        # Check we get a TypeError when decoding because transcodings aren't registered.
        data = b'{"_type_":"custom_type3_as_dict","_data_":""}'

        with self.assertRaises(TypeError) as cm:
            self.transcoder.decode(data)

        self.assertEqual(
            cm.exception.args[0],
            "Data serialized with name 'custom_type3_as_dict' is not "
            "deserializable. Please register a custom transcoding for this type.",
        )
