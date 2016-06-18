import unittest
from uuid import uuid1

from eventsourcing.domain.model.events import assert_event_handlers_empty
from eventsourcing.domain.model.log import get_log, Log
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events.python_objects_stored_events import PythonObjectsStoredEventRepository


class TestLog(unittest.TestCase):

    def setUp(self):
        assert_event_handlers_empty()

        # Setup the persistence subscriber.
        self.event_store = EventStore(PythonObjectsStoredEventRepository())
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.event_store)

    def tearDown(self):
        self.persistence_subscriber.close()
        assert_event_handlers_empty()

    def test_entity_lifecycle(self):
        log = get_log('log1', self.event_store)
        self.assertIsInstance(log, Log)
        message1 = 'This is message 1'
        message2 = 'This is message 2'
        message3 = 'This is message 3'
        message4 = 'This is message 4'
        message5 = 'This is message 5'
        message6 = 'This is message 6'
        event1 = log.append(message1)
        event2 = log.append(message2)
        event3 = log.append(message3)
        halfway = uuid1().hex
        event4 = log.append(message4)
        event5 = log.append(message5)
        event6 = log.append(message6)

        # Check we can get all the lines (query running in descending order).
        lines = list(log.get_lines())
        self.assertEqual(len(lines), 6)
        self.assertEqual(message1, lines[0])
        self.assertEqual(message2, lines[1])
        self.assertEqual(message3, lines[2])
        self.assertEqual(message4, lines[3])
        self.assertEqual(message5, lines[4])
        self.assertEqual(message6, lines[5])

        # Check we can get all the lines (query running in ascending order).
        lines = list(log.get_lines(is_ascending=True))
        self.assertEqual(len(lines), 6)
        self.assertEqual(lines[0], message1)
        self.assertEqual(lines[1], message2)
        self.assertEqual(lines[2], message3)
        self.assertEqual(lines[3], message4)
        self.assertEqual(lines[4], message5)
        self.assertEqual(lines[5], message6)

        # Check we can get lines after halfway (query running in descending order).
        lines = list(log.get_lines(after=halfway, is_ascending=False))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], message4)
        self.assertEqual(lines[1], message5)
        self.assertEqual(lines[2], message6)

        # Check we can get lines until halfway (query running in descending order).
        lines = list(log.get_lines(until=halfway, is_ascending=False))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], message1)
        self.assertEqual(lines[1], message2)
        self.assertEqual(lines[2], message3)

        # Check we can get lines until halfway (query running in ascending order).
        lines = list(log.get_lines(until=halfway, is_ascending=True))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], message1)
        self.assertEqual(lines[1], message2)
        self.assertEqual(lines[2], message3)

        # Check we can get lines after halfway (query running in ascending order).
        lines = list(log.get_lines(after=halfway, is_ascending=True))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], message4)
        self.assertEqual(lines[1], message5)
        self.assertEqual(lines[2], message6)

        # Check we can get last three lines (query running in descending order).
        lines = list(log.get_lines(limit=3, is_ascending=False))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], message4)
        self.assertEqual(lines[1], message5)
        self.assertEqual(lines[2], message6)

        # Check we can get first three lines (query running in ascending order).
        lines = list(log.get_lines(limit=3, is_ascending=True))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], message1)
        self.assertEqual(lines[1], message2)
        self.assertEqual(lines[2], message3)

        # Check we can get last line (query running in descending order).
        lines = list(log.get_lines(limit=1, after=halfway, is_ascending=False))
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], message6)

        # Check we can get the first line after halfway (query running in ascending order).
        lines = list(log.get_lines(limit=1, after=halfway, is_ascending=True))
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], message4)

        # Check we can get the first line before halfway (query running in descending order).
        lines = list(log.get_lines(limit=1, until=halfway, is_ascending=False))
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], message3)

        # Check we can get the first line (query running in ascending order).
        lines = list(log.get_lines(limit=1, until=halfway, is_ascending=True))
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], message1)

        # Check there isn't a line after the last line (query running in ascending order).
        lines = list(log.get_lines(limit=1, after=event6.domain_event_id, is_ascending=True))
        self.assertEqual(len(lines), 0)

        # Check there is nothing somehow both after and until halfway.
        lines = list(log.get_lines(after=halfway, until=halfway))
        self.assertEqual(len(lines), 0)
