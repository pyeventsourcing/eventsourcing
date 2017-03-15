from eventsourcing.infrastructure.storedevents.pythonobjectsrepo import PythonObjectsStoredEventRepository
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
from eventsourcing.tests.sequenced_item_repository_tests.base import CombinedSequencedItemRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, ThreadedStoredEventIteratorTestCase


class PythonObjectsDatastoreTestCase(AbstractDatastoreTestCase):
    def construct_datastore(self):
        return None


class PythonObjectsRepoTestCase(PythonObjectsDatastoreTestCase, CombinedSequencedItemRepositoryTestCase):

    def construct_integer_sequenced_item_repository(self):
        return PythonObjectsStoredEventRepository(
            always_write_entity_version=True,
            always_check_expected_version=True,
        )


class TestPythonObjectsStoredEventRepository(PythonObjectsRepoTestCase, StoredEventRepositoryTestCase):
    pass


class TestSimpleStoredEventIteratorWithPythonObjects(PythonObjectsRepoTestCase, SimpleStoredEventIteratorTestCase):
    pass


class TestThreadedStoredEventIteratorWithPythonObjects(PythonObjectsRepoTestCase, ThreadedStoredEventIteratorTestCase):
    pass


# Todo: Revisit this, but with threading rather than multiprocessing because data is stored in process.
# class TestConcurrentStoredEventRepositoryWithPythonObjects(PythonObjectsRepoTestCase,
# OptimisticConcurrencyControlTestCase):
#     pass
