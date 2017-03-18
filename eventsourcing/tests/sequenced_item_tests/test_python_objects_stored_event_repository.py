# from eventsourcing.infrastructure.storedevents.pythonobjectsrepo import PythonObjectsStoredEventRepository
# from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
# from eventsourcing.tests.sequenced_item_tests.base import WithActiveRecordStrategies, \
#     SimpleSequencedItemteratorTestCase, StoredEventRepositoryTestCase, ThreadedSequencedItemIteratorTestCase
#
#
# class PythonObjectsDatastoreTestCase(AbstractDatastoreTestCase):
#     def construct_datastore(self):
#         return None
#
#
# class PythonObjectsRepoTestCase(PythonObjectsDatastoreTestCase, WithActiveRecordStrategies):
#
#     def construct_integer_sequence_active_record_strategy(self):
#         return PythonObjectsStoredEventRepository(
#             always_write_entity_version=True,
#             always_check_expected_version=True,
#         )
#
#
# class TestPythonObjectsStoredEventRepository(PythonObjectsRepoTestCase, StoredEventRepositoryTestCase):
#     pass
#
#
# class TestSimpleIteratorWithPythonObjects(PythonObjectsRepoTestCase, SimpleSequencedItemteratorTestCase):
#     pass
#
#
# class TestThreadedIteratorWithPythonObjects(PythonObjectsRepoTestCase, ThreadedSequencedItemIteratorTestCase):
#     pass
#
#
# # Todo: Revisit this, but with threading rather than multiprocessing because data is stored in process.
# # class TestConcurrentStoredEventRepositoryWithPythonObjects(PythonObjectsRepoTestCase,
# # OptimisticConcurrencyControlTestCase):
# #     pass
