import unittest

from eventsourcing.tests.test_stored_events import BasicStoredEventRepositoryTestCase, SimpleStoredEventIteratorTestCase, \
    ThreadedStoredEventIteratorTestCase
from eventsourcing.infrastructure.stored_events.shared_memory_stored_events import SharedMemoryStoredEventRepository


class SharedMemoryTestCase(unittest.TestCase):

    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            stored_event_repo = SharedMemoryStoredEventRepository()
            self._stored_event_repo = stored_event_repo
            return self._stored_event_repo


class TestSharedMemoryStoredEventRepository(SharedMemoryTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithPythonObjects(SharedMemoryTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithPythonObjects(SharedMemoryTestCase, ThreadedStoredEventIteratorTestCase):
    pass
