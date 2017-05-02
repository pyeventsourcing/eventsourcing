from uuid import uuid4

from eventsourcing.domain.model.entity import AttributeChanged, TimestampedVersionedEntity, VersionedEntity, \
    mutate_entity, DomainEntity

from eventsourcing.domain.model.decorators import attribute
from eventsourcing.domain.model.events import DomainEvent, publish, subscribe, unsubscribe
from eventsourcing.example.domainmodel import Example, create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.exceptions import ConcurrencyError, MismatchedOriginatorIDError, MismatchedOriginatorVersionError, \
    MutatorRequiresTypeNotInstance, ProgrammingError, RepositoryKeyError
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
    WithCassandraActiveRecordStrategies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class TestExampleEntity(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    def test_entity_lifecycle(self):
        # Check the factory creates an instance.
        example1 = create_new_example(a=1, b=2)
        self.assertIsInstance(example1, Example)

        # Check the instance is equal to itself.
        self.assertEqual(example1, example1)

        # Check the instance is equal to a clone of itself.
        clone = object.__new__(type(example1))
        clone.__dict__.update(example1.__dict__)
        self.assertEqual(example1, clone)

        # Check the properties of the Example class.
        self.assertEqual(1, example1.a)
        self.assertEqual(2, example1.b)

        # Check the properties of the TimestampedVersionedEntity class.
        self.assertTrue(example1.id)
        self.assertEqual(1, example1.version)
        self.assertTrue(example1.created_on)
        self.assertTrue(example1.last_modified_on)
        self.assertEqual(example1.created_on, example1.last_modified_on)

        # Check a different type with the same values is not "equal" to the first.
        class Subclass(Example): pass
        other = object.__new__(Subclass)
        other.__dict__.update(example1.__dict__)
        self.assertEqual(example1.__dict__, other.__dict__)
        self.assertNotEqual(example1, other)

        # Check a second instance with the same values is not "equal" to the first.
        example2 = create_new_example(a=1, b=2)
        self.assertEqual(type(example1), type(example2))
        self.assertNotEqual(example1, example2)

        # Setup the repo.
        repo = ExampleRepository(self.entity_event_store)

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

        self.assertEqual(repo[entity1.id].created_on, entity1.created_on)
        self.assertEqual(repo[entity1.id].last_modified_on, entity1.last_modified_on)
        self.assertNotEqual(entity1.last_modified_on, entity1.created_on)

        self.assertEqual(0, entity1.count_heartbeats())
        entity1.beat_heart()
        entity1.beat_heart()
        entity1.beat_heart()
        self.assertEqual(3, entity1.count_heartbeats())
        self.assertEqual(3, repo[entity1.id].count_heartbeats())

        # Check the entity can publish multiple events simultaneously.
        entity1.beat_heart(number_of_beats=3)
        self.assertEqual(6, repo[entity1.id].count_heartbeats())

        # Check the entity can be discarded.
        entity1.discard()

        # Check the repo now raises a KeyError.
        self.assertRaises(RepositoryKeyError, repo.__getitem__, entity1.id)

        # Check the entity can't be discarded twice.
        self.assertRaises(AssertionError, entity1.discard)

        # Should fail to validate event with wrong entity ID.
        with self.assertRaises(MismatchedOriginatorIDError):
            entity2._validate_originator(
                VersionedEntity.Event(
                    originator_id=uuid4(),
                    originator_version=0
                )
            )
        # Should fail to validate event with wrong entity version.
        with self.assertRaises(MismatchedOriginatorVersionError):
            entity2._validate_originator(
                VersionedEntity.Event(
                    originator_id=entity2.id,
                    originator_version=0,
                )
            )

        # Should validate event with correct entity ID and version.
        entity2._validate_originator(
            VersionedEntity.Event(
                originator_id=entity2.id,
                originator_version=entity2.version,
            )
        )

        # Check an entity cannot be reregistered with the ID of a discarded entity.
        replacement_event = Example.Created(originator_id=entity1.id, a=11, b=12)
        with self.assertRaises(ConcurrencyError):
            publish(event=replacement_event)

    def test_not_implemented_error(self):
        # Define an event class.
        class UnsupportedEvent(DomainEvent): pass

        # Check we get an error when attempting to mutate on the event.
        self.assertRaises(NotImplementedError, Example._mutate, Example, UnsupportedEvent())

    def test_attribute(self):
        # Check we get an error when called with something other than a function.
        self.assertRaises(ProgrammingError, attribute, 'not a getter')
        self.assertRaises(ProgrammingError, attribute, 123)
        self.assertRaises(ProgrammingError, attribute, None)

        # Call the decorator with a function.
        getter = lambda: None
        p = attribute(getter)

        # Check we got a property object.
        self.assertIsInstance(p, property)

        # Check the property object has both setter and getter functions.
        self.assertTrue(p.fset)
        self.assertTrue(p.fget)

        # Pretend we decorated an object.
        entity_id = uuid4()
        o = VersionedEntity(originator_id=entity_id, originator_version=0)
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
        class Aaa(VersionedEntity):
            "An event sourced entity."

            def __init__(self, a, *args, **kwargs):
                super(Aaa, self).__init__(*args, **kwargs)
                self._a = a

            @attribute
            def a(self):
                "A mutable event sourced property."

        # Instantiate the class and check assigning to the property publishes an event and updates the object state.
        published_events = []
        subscription = (lambda x: True, lambda x: published_events.append(x))
        subscribe(*subscription)
        entity_id = uuid4()
        try:
            aaa = Aaa(originator_id=entity_id, originator_version=1, a=1)
            self.assertEqual(aaa.a, 1)
            aaa.a = 'value1'
            self.assertEqual(aaa.a, 'value1')
        finally:
            unsubscribe(*subscription)

        # Check an event was published.
        self.assertEqual(len(published_events), 1)

        # Check the published event was an AttributeChanged event, with the expected attribute values.
        published_event = published_events[0]
        self.assertIsInstance(published_event, AttributeChanged)
        self.assertEqual(published_event.name, '_a')
        self.assertEqual(published_event.value, 'value1')
        self.assertTrue(published_event.originator_version, 1)
        self.assertEqual(published_event.originator_id, entity_id)

    def test_mutator_errors(self):
        with self.assertRaises(NotImplementedError):
            TimestampedVersionedEntity._mutate(1, 2)

        # Check the guard condition raises exception.
        with self.assertRaises(MutatorRequiresTypeNotInstance):
            mutate_entity('not a class', TimestampedVersionedEntity.Created(originator_id=uuid4()))

        # Check the instantiation type error.
        with self.assertRaises(TypeError):
            # DomainEntity.Created doesn't have an originator_version,
            # so the mutator fails to construct an intance with a type
            # error from the contructor.
            mutate_entity(TimestampedVersionedEntity, DomainEntity.Created(originator_id=uuid4()))



class CustomValueObject(object):
    def __init__(self, value):
        self.value = value


class TestExampleEntityWithCassandra(WithCassandraActiveRecordStrategies, TestExampleEntity):
    pass
