import traceback
from abc import ABC, abstractmethod
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from threading import Event, Thread, get_ident
from time import sleep
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.persistence import StoredEvent


class ApplicationRecorderTestCase(TestCase, ABC):
    @abstractmethod
    def create_recorder(self):
        pass

    def test_insert_select(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        self.assertEqual(
            recorder.max_notification_id(),
            0,
        )

        # Write two stored events.
        originator_id1 = uuid4()
        originator_id2 = uuid4()

        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=0,
            topic="topic1",
            state=b"state1",
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=1,
            topic="topic2",
            state=b"state2",
        )
        stored_event3 = StoredEvent(
            originator_id=originator_id2,
            originator_version=1,
            topic="topic3",
            state=b"state3",
        )

        recorder.insert_events([stored_event1, stored_event2])
        recorder.insert_events([stored_event3])

        stored_events1 = recorder.select_events(originator_id1)
        stored_events2 = recorder.select_events(originator_id2)

        # Check we got what was written.
        self.assertEqual(len(stored_events1), 2)
        self.assertEqual(len(stored_events2), 1)

        notifications = recorder.select_notifications(1, 3)
        self.assertEqual(len(notifications), 3)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].id, 2)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b"state2")
        self.assertEqual(notifications[2].id, 3)
        self.assertEqual(notifications[2].topic, "topic3")
        self.assertEqual(notifications[2].state, b"state3")

        self.assertEqual(
            recorder.max_notification_id(),
            3,
        )

        notifications = recorder.select_notifications(1, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 1)

        notifications = recorder.select_notifications(2, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].id, 2)

        notifications = recorder.select_notifications(2, 2)
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].id, 2)
        self.assertEqual(notifications[1].id, 3)

        notifications = recorder.select_notifications(3, 1)
        self.assertEqual(len(notifications), 1, len(notifications))
        self.assertEqual(notifications[0].id, 3)

    def test_concurrent_no_conflicts(self):
        print(self)

        recorder = self.create_recorder()

        errors_happened = Event()

        counts = {}
        threads = {}
        durations = {}

        def _createevent():
            thread_id = get_ident()
            if thread_id not in threads:
                threads[thread_id] = len(threads)
            if thread_id not in counts:
                counts[thread_id] = 0
            if thread_id not in durations:
                durations[thread_id] = 0

            # thread_num = threads[thread_id]
            # count = counts[thread_id]

            originator_id = uuid4()
            stored_events = [
                StoredEvent(
                    originator_id=originator_id,
                    originator_version=i,
                    topic="topic",
                    state=b"state",
                )
                for i in range(100)
            ]
            started = datetime.now()
            # print(f"Thread {thread_num} write beginning #{count + 1}")
            try:
                recorder.insert_events(stored_events)

            except Exception:
                ended = datetime.now()
                duration = (ended - started).total_seconds()
                print(f"Error after starting {duration}")
                errors_happened.set()
                tb = traceback.format_exc()
                print(tb)
                pass
            else:
                return "OK"
            finally:
                ended = datetime.now()
                duration = (ended - started).total_seconds()
                counts[thread_id] += 1
                if duration > durations[thread_id]:
                    durations[thread_id] = duration

        stop_reading = Event()

        def read_continuously():
            while not stop_reading.is_set():
                try:
                    recorder.select_notifications(0, 10)
                except Exception:
                    errors_happened.set()
                    tb = traceback.format_exc()
                    print(tb)
                else:
                    sleep(0.01)
            self.close_db_connection()

        reader_thread = Thread(target=read_continuously)
        reader_thread.start()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(100):
                future = executor.submit(_createevent)
                futures.append(future)
            for future in futures:
                future.result()

        stop_reading.set()
        reader_thread.join()
        self.close_db_connection()

        for thread_id, thread_num in threads.items():
            count = counts[thread_id]
            duration = durations[thread_id]
            print(f"Thread {thread_num} wrote {count} times (max dur {duration})")
        self.assertFalse(errors_happened.is_set())

    def test_concurrent_throughput(self):
        print(self)

        recorder = self.create_recorder()

        errors_happened = Event()

        counts = {}
        threads = {}
        durations = {}

        # Match this to the batch page size in postgres insert for max throughput.
        NUM_EVENTS = 500

        def _createevent():
            thread_id = get_ident()
            if thread_id not in threads:
                threads[thread_id] = len(threads)
            if thread_id not in counts:
                counts[thread_id] = 0
            if thread_id not in durations:
                durations[thread_id] = 0

            originator_id = uuid4()
            stored_events = [
                StoredEvent(
                    originator_id=originator_id,
                    originator_version=i,
                    topic="topic",
                    state=b"state",
                )
                for i in range(NUM_EVENTS)
            ]

            try:
                recorder.insert_events(stored_events)

            except Exception:
                errors_happened.set()
                tb = traceback.format_exc()
                print(tb)
            finally:
                ended = datetime.now()
                duration = (ended - started).total_seconds()
                counts[thread_id] += 1
                if duration > durations[thread_id]:
                    durations[thread_id] = duration

        NUM_JOBS = 60

        with ThreadPoolExecutor(max_workers=4) as executor:
            started = datetime.now()
            futures = []
            for _ in range(NUM_JOBS):
                future = executor.submit(_createevent)
                # future.add_done_callback(self.close_db_connection)
                futures.append(future)
            for future in futures:
                future.result()

        self.assertFalse(errors_happened.is_set(), "There were errors (see above)")
        ended = datetime.now()
        print("Rate:", NUM_JOBS * NUM_EVENTS / (ended - started).total_seconds())
        self.close_db_connection()

    def close_db_connection(self, *args):
        pass
