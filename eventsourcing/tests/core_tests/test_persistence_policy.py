import unittest
from uuid import uuid4

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import VersionedEntity, TimestampedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.infrastructure.eventstore import AbstractEventStore

try:
    from unittest import mock
except:
    import mock


class TestPersistencePolicy(unittest.TestCase):
    def setUp(self):
        self.event_store = mock.Mock(spec=AbstractEventStore)
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store,
            event_type=VersionedEntity.Event
        )

    def tearDown(self):
        self.persistence_policy.close()

    def test_published_events_are_appended_to_event_store(self):
        # Check the event store's append method has NOT been called.
        assert isinstance(self.event_store, AbstractEventStore)
        self.assertEqual(0, self.event_store.append.call_count)

        # Publish a versioned entity event.
        entity_id = uuid4()
        domain_event1 = VersionedEntity.Event(originator_id=entity_id, originator_version=0)
        publish(domain_event1)

        # Check the append method has been called once with the domain event.
        self.event_store.append.assert_called_once_with(domain_event1)

        # Publish a timestamped entity event (should be ignored).
        domain_event2 = TimestampedEntity.Event(originator_id=entity_id)
        publish(domain_event2)

        # Check the append() has still only been called once with the first domain event.
        self.event_store.append.assert_called_once_with(domain_event1)
