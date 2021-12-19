from abc import ABC, abstractmethod
from timeit import timeit
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.persistence import IntegrityError, StoredEvent, Tracking


class ProcessRecorderTestCase(TestCase, ABC):
    @abstractmethod
    def create_recorder(self):
        pass

    def test_insert_select(self):
        # Construct the recorder.
        recorder = self.create_recorder()

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            0,
        )

        # Write two stored events.
        originator_id1 = uuid4()
        originator_id2 = uuid4()

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

    def test_performance(self):

        # Construct the recorder.
        recorder = self.create_recorder()

        number = 100

        notification_ids = iter(range(1, number + 1))

        def insert():
            originator_id = uuid4()

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

        duration = timeit(insert, number=number)
        print(self, f"{duration / number:.9f}")
