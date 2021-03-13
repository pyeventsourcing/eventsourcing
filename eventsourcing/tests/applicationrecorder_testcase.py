import traceback
from abc import ABC, abstractmethod
from concurrent.futures.thread import ThreadPoolExecutor
from threading import Event, Thread
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
        assert len(stored_events1) == 2
        assert len(stored_events2) == 1

        notifications = recorder.select_notifications(1, 3)
        assert len(notifications) == 3
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        assert notifications[0].topic == "topic1"
        self.assertEqual(notifications[0].state, b"state1")
        assert notifications[1].id == 2
        assert notifications[1].topic == "topic2"
        assert notifications[1].state == b"state2"
        assert notifications[2].id == 3
        assert notifications[2].topic == "topic3"
        assert notifications[2].state == b"state3"

        self.assertEqual(
            recorder.max_notification_id(),
            3,
        )

        notifications = recorder.select_notifications(1, 1)
        assert len(notifications) == 1
        assert notifications[0].id == 1

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
        recorder = self.create_recorder()

        errors_happened = Event()

        def _createevent():
            stored_event = StoredEvent(
                originator_id=uuid4(),
                originator_version=0,
                topic="topic",
                state=b"state",
            )
            try:
                recorder.insert_events([stored_event])
            except Exception:
                errors_happened.set()
                tb = traceback.format_exc()
                print(tb)
                pass
            else:
                return "OK"

        stop_reading = Event()

        def read_continuously():
            while not stop_reading.is_set():
                try:
                    recorder.select_notifications(0, 10)
                except Exception:
                    errors_happened.set()
                    tb = traceback.format_exc()
                    print(tb)

        reader_thread = Thread(target=read_continuously)
        reader_thread.start()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for _ in range(100):
                future = executor.submit(_createevent)
                futures.append(future)
            for future in futures:
                # print(future.result())
                future.result()

        stop_reading.set()
        reader_thread.join()

        self.assertFalse(errors_happened.is_set())
