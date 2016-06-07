import unittest
from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.domain.model.example import Example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepo
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository

__author__ = 'john'


class ExampleApplicationTestCase(unittest.TestCase):

    def assert_is_example_application(self, app):
        assert isinstance(app, ExampleApplication)  # For PyCharm...

        # Check there's a stored event repo.
        self.assertIsInstance(app.stored_event_repo, StoredEventRepository)

        # Check there's an event store.
        self.assertIsInstance(app.event_store, EventStore)
        self.assertEqual(app.event_store.stored_event_repo, app.stored_event_repo)

        # Check there's a persistence subscriber.
        self.assertIsInstance(app.persistence_subscriber, PersistenceSubscriber)
        self.assertEqual(app.persistence_subscriber.event_store, app.event_store)

        # Check there's an example repository.
        self.assertIsInstance(app.example_repo, ExampleRepo)

        # Register a new example.
        example1 = app.register_new_example(a=10, b=20)
        self.assertIsInstance(example1, Example)

        # Check the example is available in the repo.
        entity1 = app.example_repo[example1.id]
        self.assertEqual(10, entity1.a)
        self.assertEqual(20, entity1.b)
        self.assertEqual(example1, entity1)

        # Change attribute values.
        entity1.a = 100

        # Check the new value is available in the repo.
        entity1 = app.example_repo[example1.id]
        self.assertEqual(100, entity1.a)