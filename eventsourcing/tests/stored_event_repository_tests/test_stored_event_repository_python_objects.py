# from eventsourcing.tests.unit_test_cases import SimpleStoredEventIteratorTestCase, \
#     ThreadedStoredEventIteratorTestCase
# from eventsourcing.tests.stored_event_repository_tests.base import StoredEventRepositoryTestCase, \
#     SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase
# from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsRepoTestCase
#
#
# class TestPythonObjectsStoredEventRepository(PythonObjectsRepoTestCase, StoredEventRepositoryTestCase):
#     pass
#
#
# class TestSimpleStoredEventIteratorWithPythonObjects(PythonObjectsRepoTestCase, SimpleStoredEventIteratorTestCase):
#     pass
#
#
# class TestThreadedStoredEventIteratorWithPythonObjects(PythonObjectsRepoTestCase, ThreadedStoredEventIteratorTestCase):
#     pass
#
# # Todo: Revisit this, but with threading rather than multiprocessing because data is stored in process.
# # class TestConcurrentStoredEventRepositoryWithPythonObjects(PythonObjectsRepoTestCase,
# # OptimisticConcurrencyControlTestCase):
# #     pass
