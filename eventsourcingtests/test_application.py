import unittest
from sqlalchemy.orm.scoping import ScopedSession
from eventsourcing.application.example import ExampleApplicationWithSQLAlchemy, ExampleApplicationWithCassandra
from eventsourcing.application.main import EventSourcingApplication, EventSourcingWithCassandra
from eventsourcing.domain.model.example import Example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepository
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository


class TestExampleApplication(unittest.TestCase):

    def test(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithSQLAlchemy(db_uri='sqlite:///:memory:') as app:

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

            # Check there's an example repository.
            self.assertIsInstance(app.example_repo, ExampleRepository)

            assert isinstance(app, ExampleApplicationWithSQLAlchemy)  # For PyCharm...

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


class TestCassandraApplication(unittest.TestCase):

    def test(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithCassandra() as app:

            # Check there's an example repository.
            self.assertIsInstance(app.example_repo, ExampleRepository)

            assert isinstance(app, ExampleApplicationWithCassandra)  # For PyCharm...

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
