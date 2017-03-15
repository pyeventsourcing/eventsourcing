from eventsourcing.application.policies import NewPersistenceSubscriber
from eventsourcing.example.new_application import ExampleApplication
from eventsourcing.example.new_domain_model import Example
from eventsourcing.example.new_infrastructure import ExampleRepo
from eventsourcing.infrastructure.eventstore import AbstractEventStore, AbstractSequencedItemRepository
from eventsourcing.tests.sequenced_item_repository_tests.base import CombinedSequencedItemRepositoryTestCase


class ExampleApplicationTestCase(CombinedSequencedItemRepositoryTestCase):
    def test(self):
        """
        Checks the example application works in the way an example application should.
        """

        with self.construct_application() as app:
            # Check there's a stored event repo.
            self.assertIsInstance(app.integer_sequenced_item_repository, AbstractSequencedItemRepository)

            # Check there's an event store.
            self.assertIsInstance(app.version_entity_event_store, AbstractEventStore)
            self.assertEqual(app.version_entity_event_store.sequenced_item_repository,
                             app.integer_sequenced_item_repository)

            # Check there's a persistence subscriber.
            self.assertIsInstance(app.persistence_subscriber, NewPersistenceSubscriber)
            # Todo: Move the next two checks to the persistence subscriber unit test.
            self.assertEqual(app.persistence_subscriber.version_entity_event_store, app.version_entity_event_store)
            self.assertEqual(app.persistence_subscriber.timestamp_entity_event_store, app.timestamp_entity_event_store)

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

            # Take a snapshot of the entity.
            app.example_repo.event_player.snapshot_strategy.take_snapshot(entity1)

            # Check the new value is available in the repo.
            entity1 = app.example_repo[example1.id]
            self.assertEqual(100, entity1.a)

    def construct_application(self):
        cipher = self.construct_cipher()
        app = ExampleApplication(
            integer_sequenced_item_repository=self.integer_sequenced_item_repository,
            timestamp_sequenced_item_repository=self.timestamp_sequenced_item_repository,
            always_encrypt=bool(cipher),
            cipher=cipher,
        )
        return app

    def construct_cipher(self):
        return None
