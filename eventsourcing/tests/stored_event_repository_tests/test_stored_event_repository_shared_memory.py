# from unittest import TestCase
#
# from eventsourcing.infrastructure.storedevents.with_shared_memory import SharedMemoryStoredEventRepository
# from eventsourcing.tests.unit_test_cases import SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase
# from eventsourcing.tests.stored_event_repository_tests.base import StoredEventRepositoryTestCase, \
#     SimpleStoredEventIteratorTestCase, ThreadedStoredEventIteratorTestCase
#
#
# class SharedMemoryTestCase(TestCase):
#     @property
#     def stored_event_repo(self):
#         try:
#             return self._stored_event_repo
#         except AttributeError:
#             stored_event_repo = SharedMemoryStoredEventRepository()
#             self._stored_event_repo = stored_event_repo
#             return self._stored_event_repo
#
#
# class TestSharedMemoryStoredEventRepository(SharedMemoryTestCase, StoredEventRepositoryTestCase):
#     pass
#
#
# class TestSimpleStoredEventIteratorWithPythonObjects(SharedMemoryTestCase, SimpleStoredEventIteratorTestCase):
#     pass
#
#
# class TestThreadedStoredEventIteratorWithPythonObjects(SharedMemoryTestCase, ThreadedStoredEventIteratorTestCase):
#     pass
