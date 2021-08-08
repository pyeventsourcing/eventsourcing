from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.application import LocalNotificationLog
from eventsourcing.persistence import StoredEvent
from eventsourcing.sqlite import SQLiteApplicationRecorder, SQLiteDatastore


class TestNotificationLog(TestCase):
    def test_get_section(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()

        # Construct notification log.
        notification_log = LocalNotificationLog(recorder, section_size=5)

        # Get the "current" section of log.
        section = notification_log["1,10"]
        self.assertEqual(len(section.items), 0)  # event notifications
        self.assertEqual(section.id, None)
        self.assertEqual(section.next_id, None)

        # Write 5 events.
        originator_id = uuid4()
        for i in range(5):
            stored_event = StoredEvent(
                originator_id=originator_id,
                originator_version=i,
                topic="topic",
                state=b"state",
            )
            recorder.insert_events([stored_event])

        # Get the "head" section of log.
        section = notification_log["1,10"]
        self.assertEqual(len(section.items), 5)  # event notifications
        self.assertEqual(section.items[0].id, 1)
        self.assertEqual(section.items[1].id, 2)
        self.assertEqual(section.items[2].id, 3)
        self.assertEqual(section.items[3].id, 4)
        self.assertEqual(section.items[4].id, 5)
        self.assertEqual(section.id, "1,5")
        self.assertEqual(section.next_id, "6,10")

        # Get the "1,5" section of log.
        section = notification_log["1,5"]
        self.assertEqual(len(section.items), 5)  # event notifications
        self.assertEqual(section.items[0].id, 1)
        self.assertEqual(section.items[1].id, 2)
        self.assertEqual(section.items[2].id, 3)
        self.assertEqual(section.items[3].id, 4)
        self.assertEqual(section.items[4].id, 5)
        self.assertEqual(section.id, "1,5")
        self.assertEqual(section.next_id, "6,10")

        # Get the next section of log.
        section = notification_log["6,10"]
        self.assertEqual(len(section.items), 0)  # event notifications
        self.assertEqual(section.id, None)
        self.assertEqual(section.next_id, None)

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

        # Get the next section of log.
        section = notification_log["6,10"]
        self.assertEqual(len(section.items), 4)  # event notifications
        self.assertEqual(section.items[0].id, 6)
        self.assertEqual(section.items[1].id, 7)
        self.assertEqual(section.items[2].id, 8)
        self.assertEqual(section.items[3].id, 9)
        self.assertEqual(section.id, "6,9")
        self.assertEqual(section.next_id, None)

        # Start at non-regular section start.
        section = notification_log["3,7"]
        self.assertEqual(len(section.items), 5)  # event notifications
        self.assertEqual(section.items[0].id, 3)
        self.assertEqual(section.items[1].id, 4)
        self.assertEqual(section.items[2].id, 5)
        self.assertEqual(section.items[3].id, 6)
        self.assertEqual(section.items[4].id, 7)
        self.assertEqual(section.id, "3,7")
        self.assertEqual(section.next_id, "8,12")

        # Notification log limits section size.
        section = notification_log["3,10"]
        self.assertEqual(len(section.items), 5)  # event notifications
        self.assertEqual(section.items[0].id, 3)
        self.assertEqual(section.items[1].id, 4)
        self.assertEqual(section.items[2].id, 5)
        self.assertEqual(section.items[3].id, 6)
        self.assertEqual(section.items[4].id, 7)
        self.assertEqual(section.id, "3,7")
        self.assertEqual(section.next_id, "8,12")

        # Reader limits section size.
        section = notification_log["3,4"]
        self.assertEqual(len(section.items), 2)  # event notifications
        self.assertEqual(section.items[0].id, 3)
        self.assertEqual(section.items[1].id, 4)
        self.assertEqual(section.id, "3,4")
        self.assertEqual(section.next_id, "5,6")

        # Meaningless section ID.
        section = notification_log["3,2"]
        self.assertEqual(len(section.items), 0)  # event notifications
        self.assertEqual(section.id, None)
        self.assertEqual(section.next_id, None)

        # # Numbers below 1.
        # section = notification_log["-3,0"]
        # self.assertEqual(
        #     len(section.items), 4
        # )  # event notifications
        # self.assertEqual(section.items[0].id, 6)
        # self.assertEqual(section.items[1].id, 7)
        # self.assertEqual(section.items[2].id, 8)
        # self.assertEqual(section.items[3].id, 9)
        # self.assertEqual(section.section_id, "6,9")
        # self.assertEqual(section.next_id, None)
        #
        # section = notification_log["-4,0"]
        # self.assertEqual(
        #     len(section.items), 5
        # )  # event notifications
        # self.assertEqual(section.items[0].id, 5)
        # self.assertEqual(section.items[1].id, 6)
        # self.assertEqual(section.items[2].id, 7)
        # self.assertEqual(section.items[3].id, 8)
        # self.assertEqual(section.items[4].id, 9)
        # self.assertEqual(section.section_id, "5,9")
        # self.assertEqual(section.next_id, "10,14")
        #
        # section = notification_log["-4,-1"]
        # self.assertEqual(
        #     len(section.items), 4
        # )  # event notifications
        # self.assertEqual(section.items[0].id, 5)
        # self.assertEqual(section.items[1].id, 6)
        # self.assertEqual(section.items[2].id, 7)
        # self.assertEqual(section.items[3].id, 8)
        # self.assertEqual(section.section_id, "5,8")
        # self.assertEqual(section.next_id, "9,12")

    def test_select(self):
        recorder = SQLiteApplicationRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()

        # Construct notification log.
        notification_log = LocalNotificationLog(recorder, section_size=10)

        # Select start 1, limit 10
        notifications = notification_log.select(1, 10)
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
            recorder.insert_events([stored_event])

        # Select start 1, limit 10
        notifications = notification_log.select(1, 5)
        self.assertEqual(len(notifications), 5)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[1].id, 2)
        self.assertEqual(notifications[2].id, 3)
        self.assertEqual(notifications[3].id, 4)
        self.assertEqual(notifications[4].id, 5)

        # Select start 1, limit 10
        notifications = notification_log.select(1, 5)
        self.assertEqual(len(notifications), 5)
        self.assertEqual(notifications[0].id, 1)
        self.assertEqual(notifications[1].id, 2)
        self.assertEqual(notifications[2].id, 3)
        self.assertEqual(notifications[3].id, 4)
        self.assertEqual(notifications[4].id, 5)

        # Select start 6, limit 5
        notifications = notification_log.select(6, 5)
        self.assertEqual(len(notifications), 0)

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

        # Select start 6, limit 5
        notifications = notification_log.select(6, 5)
        self.assertEqual(len(notifications), 4)  # event notifications
        self.assertEqual(notifications[0].id, 6)
        self.assertEqual(notifications[1].id, 7)
        self.assertEqual(notifications[2].id, 8)
        self.assertEqual(notifications[3].id, 9)

        # Select start 3, limit 5
        notifications = notification_log.select(3, 5)
        self.assertEqual(len(notifications), 5)  # event notifications
        self.assertEqual(notifications[0].id, 3)
        self.assertEqual(notifications[1].id, 4)
        self.assertEqual(notifications[2].id, 5)
        self.assertEqual(notifications[3].id, 6)
        self.assertEqual(notifications[4].id, 7)

        # Notification log limits limit.
        # Select start 1, limit 20
        with self.assertRaises(ValueError) as cm:
            notification_log.select(1, 20)
        self.assertEqual(
            cm.exception.args[0], "Requested limit 20 greater than section size 10"
        )
