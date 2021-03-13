from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import LocalNotificationLog
from eventsourcing.persistence import StoredEvent
from eventsourcing.sqlite import SQLiteDatastore, SQLiteProcessRecorder
from eventsourcing.system import NotificationLogReader


class TestNotificationLogReader(TestCase):
    def test(self):
        recorder = SQLiteProcessRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()

        # Construct notification log.
        notification_log = LocalNotificationLog(recorder, section_size=5)
        reader = NotificationLogReader(
            notification_log,
        )
        notifications = list(reader.read(start=1))
        self.assertEqual(len(notifications), 0)

        # Write 5 events.
        originator_id = uuid4()
        for i in range(5):
            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=i,
                topic="topic",
                state=b"state",
            )
            recorder.insert_events(
                [stored_event],
            )

        notifications = list(reader.read(start=1))
        self.assertEqual(len(notifications), 5)

        # Write 4 events.
        originator_id = uuid4()
        for i in range(4):
            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=i,
                topic="topic",
                state=b"state",
            )
            recorder.insert_events([stored_event])

        notifications = list(reader.read(start=1))
        self.assertEqual(len(notifications), 9)

        notifications = list(reader.read(start=2))
        self.assertEqual(len(notifications), 8)

        notifications = list(reader.read(start=3))
        self.assertEqual(len(notifications), 7)

        notifications = list(reader.read(start=4))
        self.assertEqual(len(notifications), 6)

        notifications = list(reader.read(start=8))
        self.assertEqual(len(notifications), 2)

        notifications = list(reader.read(start=9))
        self.assertEqual(len(notifications), 1)

        notifications = list(reader.read(start=10))
        self.assertEqual(len(notifications), 0)
