import unittest

from eventsourcing.application.subscribers.persistence import PersistenceSubscriber

try:
    from unittest import mock
except:
    import mock
from eventsourcing.domain.model.events import publish, DomainEvent
from eventsourcing.domain.services.eventstore import AbstractEventStore


class TestPersistenceSubscriber(unittest.TestCase):

    def setUp(self):
        # Set up a persistence subscriber with a (mock) event store.
        self.event_store = mock.Mock(spec=AbstractEventStore)
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.event_store)

    def tearDown(self):
        # Close the persistence subscriber.
        self.persistence_subscriber.close()

    def test_published_events_are_appended_to_event_store(self):
        # Check the event store's append method has NOT been called.
        self.assertEqual(0, self.event_store.append.call_count)

        # Publish a (mock) domain event.
        domain_event = mock.Mock(spec=DomainEvent)
        publish(domain_event)

        # Check the append method HAS been called once with the domain event.
        self.event_store.append.assert_called_once_with(domain_event)
