from eventsourcing.tests.unit_test_cases import BasicStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, \
    ThreadedStoredEventIteratorTestCase
from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsRepoTestCase


class TestPythonObjectsStoredEventRepository(PythonObjectsRepoTestCase, BasicStoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithPythonObjects(PythonObjectsRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithPythonObjects(PythonObjectsRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass

# Todo: Revisit this, but with threading rather than multiprocessing because data is stored in process.
# class TestConcurrentStoredEventRepositoryWithPythonObjects(PythonObjectsRepoTestCase,
# OptimisticConcurrencyControlTestCase):
#     pass
