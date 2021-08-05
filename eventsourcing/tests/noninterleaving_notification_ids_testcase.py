from abc import ABC, abstractmethod
from threading import Event, Thread
from unittest import TestCase
from uuid import uuid4

from eventsourcing.persistence import ApplicationRecorder, StoredEvent


class NonInterleavingNotificationIDsBaseCase(ABC, TestCase):
    insert_num = 1000

    def test(self):
        recorder = self.create_recorder()

        race_started = Event()

        originator1_id = uuid4()
        originator2_id = uuid4()

        stack1 = self.create_stack(originator1_id)
        stack2 = self.create_stack(originator2_id)

        def insert_stack1():
            race_started.wait()
            recorder.insert_events(stack1)

        def insert_stack2():
            race_started.wait()
            recorder.insert_events(stack2)

        thread1 = Thread(target=insert_stack1)
        thread1.setDaemon(True)

        thread2 = Thread(target=insert_stack2)
        thread2.setDaemon(True)

        thread1.start()
        thread2.start()
        race_started.set()
        thread1.join()
        thread2.join()

        notifications = recorder.select_notifications(start=1, limit=1000000)
        ids_for_sequence1 = [
            e.id for e in notifications if e.originator_id == originator1_id
        ]
        ids_for_sequence2 = [
            e.id for e in notifications if e.originator_id == originator2_id
        ]
        max_id_for_sequence1 = max(ids_for_sequence1)
        max_id_for_sequence2 = max(ids_for_sequence2)
        min_id_for_sequence1 = min(ids_for_sequence1)
        min_id_for_sequence2 = min(ids_for_sequence2)

        if max_id_for_sequence1 > min_id_for_sequence2:
            self.assertGreater(min_id_for_sequence1, max_id_for_sequence2)
        else:
            self.assertGreater(min_id_for_sequence2, max_id_for_sequence1)

    def create_stack(self, originator_id):
        return [
            StoredEvent(
                originator_id=originator_id,
                originator_version=i,
                topic="",
                state=b"",
            )
            for i in range(self.insert_num)
        ]

    @abstractmethod
    def create_recorder(self) -> ApplicationRecorder:
        pass
