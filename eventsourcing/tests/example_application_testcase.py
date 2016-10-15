from eventsourcing.application.example.base import ExampleApplication
from eventsourcing.domain.model.example import Example
from eventsourcing.tests.test_stored_events import AbstractTestCase
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepo
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository


class ApplicationTestCase(AbstractTestCase):

    def create_app(self):
        raise NotImplementedError

    def setUp(self):
        super(ApplicationTestCase, self).setUp()
        self.app = self.create_app()

    def tearDown(self):
        self.app.close()
        super(ApplicationTestCase, self).tearDown()


class ExampleApplicationTestCase(ApplicationTestCase):

    def test(self):
        """
        Checks application works in the way an ExampleApplication should do.
        """

        # Check we're dealing with an example application.
        assert isinstance(self.app, ExampleApplication)

        # Check there's a stored event repo.
        self.assertIsInstance(self.app.stored_event_repo, StoredEventRepository)

        # Check there's an event store.
        self.assertIsInstance(self.app.event_store, EventStore)
        self.assertEqual(self.app.event_store.stored_event_repo, self.app.stored_event_repo)

        # Check there's a persistence subscriber.
        self.assertIsInstance(self.app.persistence_subscriber, PersistenceSubscriber)
        self.assertEqual(self.app.persistence_subscriber.event_store, self.app.event_store)

        # Check there's an example repository.
        self.assertIsInstance(self.app.example_repo, ExampleRepo)

        # Register a new example.
        example1 = self.app.register_new_example(a=10, b=20)
        self.assertIsInstance(example1, Example)

        # Check the example is available in the repo.
        entity1 = self.app.example_repo[example1.id]
        self.assertEqual(10, entity1.a)
        self.assertEqual(20, entity1.b)
        self.assertEqual(example1, entity1)

        # Change attribute values.
        entity1.a = 100

        # Check the new value is available in the repo.
        entity1 = self.app.example_repo[example1.id]
        self.assertEqual(100, entity1.a)
