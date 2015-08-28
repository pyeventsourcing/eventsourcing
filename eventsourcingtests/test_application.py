import unittest
from sqlalchemy.orm.scoping import ScopedSession
from eventsourcing.application.example import ExampleApplication
from eventsourcing.application.main import EventSourcedApplication
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events import StoredEventRepository


class TestEventSourcedApplication(unittest.TestCase):

    def test(self):
        # Setup an event sourced application, use it as a context manager.
        with EventSourcedApplication() as app:

            # Check there's a DB session.
            self.assertIsInstance(app.db_session, ScopedSession)

            # Check there's a stored event repo.
            self.assertIsInstance(app.stored_event_repo, StoredEventRepository)
            self.assertEqual(app.stored_event_repo.db_session, app.db_session)

            # Check there's an event store.
            self.assertIsInstance(app.event_store, EventStore)
            self.assertEqual(app.event_store.stored_event_repo, app.stored_event_repo)

            # Check there's a persistence subscriber.
            self.assertIsInstance(app.persistence_subscriber, PersistenceSubscriber)
            self.assertEqual(app.persistence_subscriber.event_store, app.event_store)


class TestExampleApplication(unittest.TestCase):

    def test(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplication() as app:

            # Check there's an example repository.
            self.assertIsInstance(app.example_repo, ExampleRepository)

            assert isinstance(app, ExampleApplication)  # For PyCharm...

            # Register a new example.
            example1 = app.register_new_example(a=10, b=20)

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
