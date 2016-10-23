from unittest import TestCase

from eventsourcing.infrastructure.stored_event_repos.with_shared_memory import SharedMemoryStoredEventRepository
from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, SimpleStoredEventIteratorTestCase, \
    ThreadedStoredEventIteratorTestCase


class SharedMemoryTestCase(TestCase):

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
