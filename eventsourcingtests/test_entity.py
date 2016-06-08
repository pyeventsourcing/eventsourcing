import unittest
import mock

from eventsourcing.domain.model.entity import mutableproperty, EntityIDConsistencyError, EntityVersionConsistencyError, \
    EventSourcedEntity, created_mutator, MutatorRequiresTypeError
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.domain.model.example import register_new_example, Example
from eventsourcing.domain.model.exceptions import ConsistencyError
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

        # Check the properties of the Example class.
        self.assertEqual(1, example1.a)
        self.assertEqual(2, example1.b)

        # Check the properties of the EventSourcedEntity class.
        self.assertTrue(example1.id)
        self.assertEqual(1, example1.version)
        self.assertTrue(example1.created_on)

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

        # Check the entity can't be discarded twice.
        self.assertRaises(AssertionError, entity1.discard)

        # Should fail to validate event with wrong entity ID.
        self.assertRaises(EntityIDConsistencyError,
                          entity2._validate_originator,
                          DomainEvent(entity_id=entity2.id+'wrong', entity_version=0)
                          )
        # Should fail to validate event with wrong entity version.
        self.assertRaises(EntityVersionConsistencyError,
                          entity2._validate_originator,
                          DomainEvent(entity_id=entity2.id, entity_version=0)
                          )
        # Should validate event with correct entity ID and version.
        entity2._validate_originator(
            DomainEvent(entity_id=entity2.id, entity_version=entity2.version)
        )

    def test_not_implemented_error(self):
        # Define an event class.
        class UnsupportedEvent(DomainEvent): pass

        # Check we get an error when attempting to mutate on the event.
        self.assertRaises(NotImplementedError, Example.mutate, Example, UnsupportedEvent('1', '0'))

    def test_mutableproperty(self):
        # Check we get a property object when called with a function.
        getter = lambda: 'value'
        p = mutableproperty(getter)
        self.assertIsInstance(p, property)
        self.assertTrue(p.fset)
        self.assertTrue(p.fget)
        self.assertEqual(p.fget, getter)

        # Check we get an error when called with something other than a function.
        self.assertRaises(ValueError, mutableproperty, 'not a getter')
        self.assertRaises(ValueError, mutableproperty, 123)
        self.assertRaises(ValueError, mutableproperty, None)

    def test_static_mutator_method(self):
        self.assertRaises(NotImplementedError, EventSourcedEntity._mutator, 1, 2)

    def test_created_mutator_error(self):
        self.assertRaises(MutatorRequiresTypeError, created_mutator, mock.Mock(spec=DomainEvent), 'not a class')