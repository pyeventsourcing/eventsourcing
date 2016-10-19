import unittest

from eventsourcing.infrastructure.stored_events.python_objects_stored_events import PythonObjectsStoredEventRepository
from eventsourcing.tests.test_stored_events import BasicStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase, ConcurrentStoredEventRepositoryTestCase


class PythonObjectsTestCase(unittest.TestCase):

    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            stored_event_repo = PythonObjectsStoredEventRepository()
            self._stored_event_repo = stored_event_repo
            return stored_event_repo


class TestPythonObjectsStoredEventRepository(PythonObjectsTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithPythonObjects(PythonObjectsTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithPythonObjects(PythonObjectsTestCase, ThreadedStoredEventIteratorTestCase):
    pass


# Todo: Revisit this, but with threading rather than multiprocessing because data is stored in process.
# class TestConcurrentStoredEventRepositoryWithPythonObjects(PythonObjectsTestCase, ConcurrentStoredEventRepositoryTestCase):
#     pass
