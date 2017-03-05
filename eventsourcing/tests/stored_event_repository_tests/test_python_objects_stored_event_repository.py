from eventsourcing.infrastructure.storedevents.pythonobjectsrepo import PythonObjectsStoredEventRepository
from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase
from eventsourcing.tests.stored_event_repository_tests.base import AbstractStoredEventRepositoryTestCase, \
    SimpleStoredEventIteratorTestCase, StoredEventRepositoryTestCase, ThreadedStoredEventIteratorTestCase


class PythonObjectsDatastoreTestCase(AbstractDatastoreTestCase):
    def construct_datastore(self):
        return None


class PythonObjectsRepoTestCase(PythonObjectsDatastoreTestCase, AbstractStoredEventRepositoryTestCase):

    def construct_stored_event_repo(self):
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
