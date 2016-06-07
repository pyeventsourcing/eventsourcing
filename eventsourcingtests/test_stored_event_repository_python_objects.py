from eventsourcing.infrastructure.stored_events.python_objects_stored_events import PythonObjectsStoredEventRepository
from eventsourcingtests.test_stored_events import StoredEventRepositoryTestCase


class TestPythonObjectsStoredEventRepository(StoredEventRepositoryTestCase):

    def test_stored_events_in_memory(self):
        self.checkStoredEventRepository(PythonObjectsStoredEventRepository())