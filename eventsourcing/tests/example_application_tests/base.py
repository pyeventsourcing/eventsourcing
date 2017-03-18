from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.example.application import ExampleApplication
from eventsourcing.example.domainmodel import Example
from eventsourcing.example.infrastructure import ExampleRepo
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.eventstore import AbstractEventStore
from eventsourcing.tests.sequenced_item_tests.base import WithActiveRecordStrategies


class ExampleApplicationTestCase(WithActiveRecordStrategies):
    def test(self):
        """
        Checks the example application works in the way an example application should.
        """

        with self.construct_application() as app:
            # Check there's a stored event repo.
            self.assertIsInstance(app.integer_sequenced_active_record_strategy, AbstractActiveRecordStrategy)

            # Check there's an event store for version entity events.
            self.assertIsInstance(app.version_entity_event_store, AbstractEventStore)
            self.assertEqual(app.version_entity_event_store.active_record_strategy,
                             app.integer_sequenced_active_record_strategy)

            # Check there's an event store for timestamp entity events.
            self.assertIsInstance(app.timestamp_entity_event_store, AbstractEventStore)
            self.assertEqual(app.timestamp_entity_event_store.active_record_strategy,
                             app.timestamp_sequenced_active_record_strategy)

            # Check there's a persistence subscriber.
            self.assertIsInstance(app.persistence_subscriber, PersistencePolicy)
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
            entity1.a = 50

            # Check the attribute has the new value.
            self.assertEqual(50, entity1.a)

            # Check the new value is available in the repo.
            entity1 = app.example_repo[example1.id]
            self.assertEqual(50, entity1.a)

            # Take a snapshot of the entity.
            snapshot1 = app.example_repo.event_player.take_snapshot(entity1.id)

            # Take another snapshot of the entity (should be the same event).
            snapshot2 = app.example_repo.event_player.take_snapshot(entity1.id)
            self.assertEqual(snapshot1, snapshot2)

            # Check the snapshot exists.
            snapshot3 = app.example_repo.event_player.snapshot_strategy.get_snapshot(entity1.id)
            self.assertIsInstance(snapshot3, Snapshot)
            self.assertEqual(snapshot1, snapshot3)

            # Change attribute values.
            entity1.a = 100

            # Check the attribute has the new value.
            self.assertEqual(100, entity1.a)

            # Check the new value is available in the repo.
            entity1 = app.example_repo[example1.id]
            self.assertEqual(100, entity1.a)

            # Take another snapshot of the entity.
            snapshot4 = app.example_repo.event_player.take_snapshot(entity1.id)

            # Check the new snapshot is not equal to the first.
            self.assertNotEqual(snapshot1, snapshot4)

    def construct_application(self):
        cipher = self.construct_cipher()
        app = ExampleApplication(
            integer_sequenced_active_record_strategy=self.integer_sequence_active_record_strategy,
            timestamp_sequenced_active_record_strategy=self.timestamp_sequence_active_record_strategy,
            always_encrypt=bool(cipher),
            cipher=cipher,
        )
        return app

    def construct_cipher(self):
        return None
