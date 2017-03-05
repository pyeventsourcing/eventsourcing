import unittest

from eventsourcing.application.policies import PersistenceSubscriber

try:
    from unittest import mock
except:
    import mock
from eventsourcing.domain.model.events import publish, DomainEvent
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class TestPersistenceSubscriber(unittest.TestCase):

    def tearDown(self):
        # Close the persistence subscriber.
        self.persistence_subscriber.close()

    def test_published_events_are_appended_to_event_store(self):
        # Setup the persistence subscriber with an event store.
        event_store = mock.Mock(spec=AbstractEventStore)
        self.persistence_subscriber = PersistenceSubscriber(event_store=event_store)

        # Check the event store's append method has NOT been called.
        assert isinstance(event_store, AbstractEventStore)
        self.assertEqual(0, event_store.append.call_count)

        # Publish a (mock) domain event.
        domain_event = mock.Mock(spec=DomainEvent)
        publish(domain_event)

        # Check the append method HAS been called once with the domain event.
        event_store.append.assert_called_once_with(domain_event)
