import unittest
from uuid import uuid4

from eventsourcing.application.policies import PersistencePolicy, SnapshottingPolicy
from eventsourcing.domain.model.entity import VersionedEntity, TimestampedEntity, AbstractEntityRepository
from eventsourcing.domain.model.events import publish
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
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
            persist_event_type=VersionedEntity.Event
        )

    def tearDown(self):
        self.persistence_policy.close()

    def test_published_events_are_appended_to_event_store(self):
        # Check the event store's append method has NOT been called.
        assert isinstance(self.event_store, AbstractEventStore)
        self.assertEqual(0, self.event_store.store.call_count)

        # Publish a versioned entity event.
        entity_id = uuid4()
        domain_event1 = VersionedEntity.Event(
            originator_id=entity_id,
            originator_version=0,
        )
        publish(domain_event1)

        # Check the append method has been called once with the domain event.
        self.event_store.store.assert_called_once_with(domain_event1)

        # Publish a timestamped entity event (should be ignored).
        domain_event2 = TimestampedEntity.Event(
            originator_id=entity_id,
        )
        publish(domain_event2)

        # Check the append() has still only been called once with the first domain event.
        self.event_store.store.assert_called_once_with(domain_event1)


class TestSnapshottingPolicy(unittest.TestCase):
    def setUp(self):
        self.repository = mock.Mock(spec=AbstractEntityRepository)
        self.snapshot_store = mock.Mock(spec=AbstractEventStore)
        self.policy = SnapshottingPolicy(
            repository=self.repository,
            snapshot_store=self.snapshot_store,
            period=2,
        )

    def tearDown(self):
        self.policy.close()

    def test_published_events_are_appended_to_event_store(self):
        # Check the event store's append method has NOT been called.
        assert isinstance(self.repository, AbstractEntityRepository)
        self.assertEqual(0, self.repository.take_snapshot.call_count)

        # Publish a versioned entity event.
        entity_id = uuid4()
        domain_event1 = VersionedEntity.Event(
            originator_id=entity_id,
            originator_version=0,
        )
        domain_event2 = VersionedEntity.Event(
            originator_id=entity_id,
            originator_version=1,
        )

        # Check take_snapshot is called once for each event.
        publish(domain_event1)
        self.assertEqual(0, self.repository.take_snapshot.call_count)
        publish(domain_event2)
        self.assertEqual(1, self.repository.take_snapshot.call_count)

        # Check take_snapshot is called once for each list.
        publish([domain_event1, domain_event2])
        self.assertEqual(2, self.repository.take_snapshot.call_count)

