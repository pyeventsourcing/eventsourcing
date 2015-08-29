import unittest
try:
    from unittest import mock
except:
    import mock
from eventsourcing.domain.model.events import publish, DomainEvent
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber


class TestPersistenceSubscriber(unittest.TestCase):

    def setUp(self):
        self.mock_event_store = mock.Mock(spec=EventStore)
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.mock_event_store)

    def tearDown(self):
        self.persistence_subscriber.close()

    def test(self):
        # Check the publishing a domain event causes 'append' to be called on the event store.
        self.assertEqual(0, self.mock_event_store.append.call_count)
        publish(mock.Mock(spec=DomainEvent))
        self.assertEqual(1, self.mock_event_store.append.call_count)
