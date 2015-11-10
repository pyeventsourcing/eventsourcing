import unittest

from sqlalchemy.orm.scoping import ScopedSession

from eventsourcing.application.example.with_sqlalchemy import ExampleApplicationWithSQLAlchemy
from eventsourcing.domain.model.example import Example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository
from eventsourcingtests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithSQLAlchemy(ExampleApplicationTestCase):

    def test_application_with_cassandra(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithSQLAlchemy(db_uri='sqlite:///:memory:') as app:
            self.assert_is_example_application(app)
