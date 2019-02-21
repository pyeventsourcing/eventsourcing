from unittest import TestCase
from uuid import uuid4

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore
from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord


class TestFactory(TestCase):
    def test_construct_sqlalchemy_eventstore(self):
        # Construct the infrastructure.
        datastore = SQLAlchemyDatastore(settings=SQLAlchemySettings())
        datastore.setup_connection()

        event_store = construct_sqlalchemy_eventstore(
            session=datastore.session,
            contiguous_record_ids=True,
            application_name=uuid4().hex,
        )
        datastore.setup_table(event_store.record_manager.record_class)

        self.assertIsInstance(event_store, EventStore)

        # Store an event.
        aggregate_id = uuid4()
        aggregate_version = 0
        domain_event = DomainEvent(
            a=1,
            originator_id=aggregate_id,
            originator_version=aggregate_version,
        )
        event_store.store(domain_event)

        # Get the domain events.
        events = event_store.get_domain_events(originator_id=aggregate_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], domain_event)

        # Test the while clause of all_sequence_ids() is filtering on application_name.
        self.assertEqual(event_store.record_manager.record_class, StoredEventRecord)
        sequence_ids = event_store.record_manager.list_sequence_ids()
        self.assertEqual([aggregate_id], sequence_ids)

        # - check the aggregate ID isn't listed by another application
        event_store = construct_sqlalchemy_eventstore(
            session=datastore.session,
            contiguous_record_ids=True,
            application_name=uuid4().hex,
        )
        sequence_ids = event_store.record_manager.list_sequence_ids()
        self.assertEqual([], sequence_ids)
