from unittest import TestCase
from uuid import uuid4

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore


class TestFactory(TestCase):
    def test_construct_sqlalchemy_eventstore(self):

        datastore = SQLAlchemyDatastore(settings=SQLAlchemySettings())
        datastore.setup_connection()

        event_store = construct_sqlalchemy_eventstore(datastore.session)
        datastore.setup_table(event_store.record_manager.record_class)

        self.assertIsInstance(event_store, EventStore)

        aggregate_id = uuid4()
        aggregate_version = 0
        domain_event = DomainEvent(
            a=1,
            originator_id=aggregate_id,
            originator_version=aggregate_version,
        )
        event_store.append(domain_event)
        events = event_store.get_domain_events(originator_id=aggregate_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], domain_event)
