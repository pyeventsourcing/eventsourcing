from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, SimpleStoredEventIteratorTestCase, \
    ThreadedStoredEventIteratorTestCase
from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsTestCase


class TestPythonObjectsStoredEventRepository(PythonObjectsTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithPythonObjects(PythonObjectsTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithPythonObjects(PythonObjectsTestCase, ThreadedStoredEventIteratorTestCase):
    pass


# Todo: Revisit this, but with threading rather than multiprocessing because data is stored in process.
# class TestConcurrentStoredEventRepositoryWithPythonObjects(PythonObjectsTestCase, ConcurrentStoredEventRepositoryTestCase):
#     pass
