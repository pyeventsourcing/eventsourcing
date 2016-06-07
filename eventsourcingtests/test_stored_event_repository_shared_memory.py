from eventsourcing.infrastructure.stored_events.shared_memory_stored_events import SharedMemoryStoredEventRepository
from eventsourcingtests.test_stored_events import StoredEventRepositoryTestCase


class TestSharedMemoryStoredEventRepository(StoredEventRepositoryTestCase):

    def test_stored_events_in_shared_memory(self):
        self.checkStoredEventRepository(SharedMemoryStoredEventRepository())