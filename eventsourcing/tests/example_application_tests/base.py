from eventsourcing.application.policies import PersistenceSubscriber
from eventsourcing.example.application import ExampleApplication
from eventsourcing.example.domain_model import Example
from eventsourcing.example.infrastructure import ExampleRepo
from eventsourcing.infrastructure.eventstore import AbstractEventStore, AbstractStoredEventRepository
from eventsourcing.tests.stored_event_repository_tests.base import AbstractStoredEventRepositoryTestCase


class ExampleApplicationTestCase(AbstractStoredEventRepositoryTestCase):

    def test(self):
        """
        Checks the example application works in the way an example application should.
        """

        with self.construct_application() as app:
            # Check there's a stored event repo.
            self.assertIsInstance(app.stored_event_repository, AbstractStoredEventRepository)

            # Check there's an event store.
            self.assertIsInstance(app.event_store, AbstractEventStore)
            self.assertEqual(app.event_store.stored_event_repo, app.stored_event_repository)

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

    def construct_application(self):
        app = ExampleApplication(
            stored_event_repository=self.stored_event_repo,
            cipher=self.construct_cipher(),
        )
        return app

    def construct_cipher(self):
        return None
