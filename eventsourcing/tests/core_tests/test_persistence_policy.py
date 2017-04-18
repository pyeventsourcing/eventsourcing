import unittest

from eventsourcing.application.policies import CombinedPersistencePolicy, TimestampedEntityEvent
from eventsourcing.domain.model.events import VersionedEntityEvent, publish
from eventsourcing.infrastructure.eventstore import AbstractEventStore

try:
    from unittest import mock
except:
    import mock


class TestCombinedPersistencePolicy(unittest.TestCase):
    def setUp(self):
        self.ve_es = mock.Mock(spec=AbstractEventStore)
        self.te_es = mock.Mock(spec=AbstractEventStore)
        self.sn_es = mock.Mock(spec=AbstractEventStore)
        self.policy = CombinedPersistencePolicy(
            versioned_entity_event_store=self.ve_es,
            timestamped_entity_event_store=self.te_es,
            snapshot_store=self.sn_es,
        )

    def tearDown(self):
        self.policy.close()

    def test_published_events_are_appended_to_event_store(self):
        # Check the event store's append method has NOT been called.
        assert isinstance(self.ve_es, AbstractEventStore)
        assert isinstance(self.te_es, AbstractEventStore)
        self.assertEqual(0, self.ve_es.append.call_count)
        self.assertEqual(0, self.te_es.append.call_count)

        # Publish a (mock) versioned entity event.
        domain_event1 = mock.Mock(spec=VersionedEntityEvent)
        publish(domain_event1)

        # Check the append method HAS been called once with the domain event.
        self.ve_es.append.assert_called_once_with(domain_event1)
        self.assertEqual(0, self.te_es.append.call_count)

        # Publish a (mock) timestamp entity event.
        domain_event2 = mock.Mock(spec=TimestampedEntityEvent)
        publish(domain_event2)

        # Check the append method HAS been called once with the domain event.
        self.ve_es.append.assert_called_once_with(domain_event1)
        self.te_es.append.assert_called_once_with(domain_event2)
