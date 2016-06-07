import unittest
from eventsourcing.domain.model.events import DomainEvent

from eventsourcing.domain.model.example import register_new_example, Example
from eventsourcing.infrastructure.event_sourced_repos.example_repo import ExampleRepo
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.persistence_subscriber import PersistenceSubscriber
from eventsourcing.infrastructure.stored_events.python_objects_stored_events import PythonObjectsStoredEventRepository


class TestExampleEntity(unittest.TestCase):

    def setUp(self):
        # Setup the persistence subscriber.
        self.event_store = EventStore(PythonObjectsStoredEventRepository())
        self.persistence_subscriber = PersistenceSubscriber(event_store=self.event_store)

    def tearDown(self):
        self.persistence_subscriber.close()

    def test_entity_lifecycle(self):
        # Check the factory creates an instance.
        example1 = register_new_example(a=1, b=2)
        self.assertIsInstance(example1, Example)
        self.assertEqual(1, example1.a)
        self.assertEqual(2, example1.b)

        # Check a second instance with the same values is not "equal" to the first.
        example2 = register_new_example(a=1, b=2)
        self.assertNotEqual(example1, example2)

        # Setup the repo.
        repo = ExampleRepo(self.event_store)

        # Check the example entities can be retrieved from the example repository.
        entity1 = repo[example1.id]
        self.assertIsInstance(entity1, Example)
        self.assertEqual(1, entity1.a)
        self.assertEqual(2, entity1.b)

        entity2 = repo[example2.id]
        self.assertIsInstance(entity2, Example)
        self.assertEqual(1, entity2.a)
        self.assertEqual(2, entity2.b)

        # Check the entity can be updated.
        entity1.a = 100
        self.assertEqual(100, repo[entity1.id].a)
        entity1.b = -200
        self.assertEqual(-200, repo[entity1.id].b)

        self.assertEqual(0, entity1.count_heartbeats())
        entity1.beat_heart()
        entity1.beat_heart()
        entity1.beat_heart()
        self.assertEqual(3, entity1.count_heartbeats())
        self.assertEqual(3, repo[entity1.id].count_heartbeats())

        # Check the entity can be discarded.
        entity1.discard()

        # Check the repo now raises a KeyError.
        self.assertRaises(KeyError, repo.__getitem__, entity1.id)

    def test_not_implemented_error(self):
        # Define an event class.
        class UnsupportedEvent(DomainEvent): pass

        # Check we get an error when attempting to mutate on the event.
        self.assertRaises(NotImplementedError, Example.mutate, Example, UnsupportedEvent('1', '0'))
