import unittest
import mock

from eventsourcing.domain.model.entity import mutableproperty, EntityIDConsistencyError, EntityVersionConsistencyError, \
    EventSourcedEntity, created_mutator, CreatedMutatorRequiresTypeNotInstance
from eventsourcing.domain.model.events import DomainEvent, subscribe, unsubscribe, assert_event_handlers_empty, publish
from eventsourcing.domain.model.example import register_new_example, Example
from eventsourcing.exceptions import ProgrammingError, RepositoryKeyError
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
        assert_event_handlers_empty()

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
        self.assertRaises(RepositoryKeyError, repo.__getitem__, entity1.id)

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

        # Check an entity can be reregistered with the same ID.
        replacement_event = Example.Created(entity_id=entity1.id, a=11, b=12)
        # replacement = Example.mutate(event=replacement_event)
        publish(event=replacement_event)

        # Check the replacement entity can be retrieved from the example repository.
        replacement = repo[entity1.id]
        assert isinstance(replacement, Example)
        self.assertEqual(replacement.a, 11)
        self.assertEqual(replacement.b, 12)

    def test_not_implemented_error(self):
        # Define an event class.
        class UnsupportedEvent(DomainEvent): pass

        # Check we get an error when attempting to mutate on the event.
        self.assertRaises(NotImplementedError, Example.mutate, Example, UnsupportedEvent('1', '0'))

    def test_mutableproperty(self):
        # Check we get an error when called with something other than a function.
        self.assertRaises(ProgrammingError, mutableproperty, 'not a getter')
        self.assertRaises(ProgrammingError, mutableproperty, 123)
        self.assertRaises(ProgrammingError, mutableproperty, None)

        # Call the decorator with a function.
        getter = lambda: None
        p = mutableproperty(getter)

        # Check we got a property object.
        self.assertIsInstance(p, property)

        # Check the property object has both setter and getter functions.
        self.assertTrue(p.fset)
        self.assertTrue(p.fget)

        # Pretend we decorated an object.
        o = EventSourcedEntity(entity_id='1', entity_version=0, domain_event_id=1)
        o.__dict__['_<lambda>'] = 'value1'

        # Call the property's getter function.
        value = p.fget(o)
        self.assertEqual(value, 'value1')

        # Call the property's setter function.
        p.fset(o, 'value2')

        # Check the attribute has changed.
        value = p.fget(o)
        self.assertEqual(value, 'value2')

        # Check the property's getter function isn't the getter function we passed in.
        self.assertNotEqual(p.fget, getter)

        # Define a class that uses the decorator.
        class Aaa(EventSourcedEntity):
            "An event sourced entity."

            def __init__(self, a, *args, **kwargs):
                super(Aaa, self).__init__(*args, **kwargs)
                self._a = a

            @mutableproperty
            def a(self):
                "A mutable event sourced property."

        # Instantiate the class and check assigning to the property publishes an event and updates the object state.
        published_events = []
        subscription = (lambda x: True, lambda x: published_events.append(x))
        subscribe(*subscription)
        entity_id = '1'
        try:
            aaa = Aaa(entity_id=entity_id, entity_version=None, domain_event_id='0', a=1)
            self.assertEqual(aaa.a, 1)
            aaa.a = 'value1'
            self.assertEqual(aaa.a, 'value1')
        finally:
            unsubscribe(*subscription)

        # Check an event was published.
        self.assertEqual(len(published_events), 1)

        # Check the published event was an AttributeChanged event, with the expected attribute values.
        published_event = published_events[0]
        self.assertIsInstance(published_event, Aaa.AttributeChanged)
        self.assertEqual(published_event.name, '_a')
        self.assertEqual(published_event.value, 'value1')
        self.assertTrue(published_event.domain_event_id)
        self.assertEqual(published_event.entity_id, entity_id)

    def test_static_mutator_method(self):
        self.assertRaises(NotImplementedError, EventSourcedEntity._mutator, 1, 2)

    def test_created_mutator_error(self):
        self.assertRaises(CreatedMutatorRequiresTypeNotInstance, created_mutator, mock.Mock(spec=DomainEvent), 'not a class')
