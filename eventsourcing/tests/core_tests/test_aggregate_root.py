import uuid
from uuid import uuid4

import mock

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.aggregate_root import AggregateCreated, AggregateEvent, AggregateRoot, \
    aggregate_mutator
from eventsourcing.domain.model.entity import MismatchedOriginatorIDError, MismatchedOriginatorVersionError, \
    attribute, singledispatch
from eventsourcing.exceptions import MutatorRequiresTypeNotInstance
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, \
    SqlIntegerSequencedItem
from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicies
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class TestExampleAggregateRoot(WithSQLAlchemyActiveRecordStrategies, WithPersistencePolicies):
    def setUp(self):
        super(TestExampleAggregateRoot, self).setUp()
        self.app = ExampleDDDApplication(self.datastore)

    def tearDown(self):
        self.app.close()
        super(TestExampleAggregateRoot, self).tearDown()

    def test_aggregate_lifecycle(self):
        # Create a new aggregate.
        aggregate = self.app.create_example_aggregate()

        # Check it does not exist in the repository.
        self.assertNotIn(aggregate.id, self.app.aggregate_repository)

        # Save the aggregate.
        aggregate.save()

        # Check it now exists in the repository.
        self.assertIn(aggregate.id, self.app.aggregate_repository)

        # Change an attribute of the aggregate root entity.
        self.assertNotEqual(aggregate.foo, 'bar')
        aggregate.foo = 'bar'
        self.assertEqual(aggregate.foo, 'bar')
        self.assertNotEqual(self.app.aggregate_repository[aggregate.id].foo, 'bar')
        aggregate.save()
        self.assertEqual(self.app.aggregate_repository[aggregate.id].foo, 'bar')

        # Check the aggregate has zero entities.
        self.assertEqual(aggregate.count_entities(), 0)

        # Check the aggregate has zero entities.
        self.assertEqual(aggregate.count_entities(), 0)

        # Ask the aggregate to create an entity within itself.
        aggregate.create_new_entity()

        # Check the aggregate has one entity.
        self.assertEqual(aggregate.count_entities(), 1)

        # Check the aggregate in the repo still has zero entities.
        self.assertEqual(self.app.aggregate_repository[aggregate.id].count_entities(), 0)

        # Call save().
        aggregate.save()

        # Check the aggregate in the repo now has one entity.
        self.assertEqual(self.app.aggregate_repository[aggregate.id].count_entities(), 1)

        # Create two more entities within the aggregate.
        aggregate.create_new_entity()
        aggregate.create_new_entity()

        # Save both "entity created" events in one atomic transaction.
        aggregate.save()

        # Check the aggregate in the repo now has three entities.
        self.assertEqual(self.app.aggregate_repository[aggregate.id].count_entities(), 3)

        # Discard the aggregate, but don't call save() yet.
        aggregate.discard()

        # Check the aggregate still exists in the repo.
        self.assertIn(aggregate.id, self.app.aggregate_repository)

        # Call save().
        aggregate.save()

        # Check the aggregate no longer exists in the repo.
        self.assertNotIn(aggregate.id, self.app.aggregate_repository)

    def test_mismatched_originator_errors(self):
        # Create a new aggregate.
        aggregate = self.app.create_example_aggregate()

        # Check a different created event fails to validate IDs.
        with self.assertRaises(MismatchedOriginatorIDError):
            aggregate._validate_originator_id(AggregateCreated(originator_id=uuid4()))

        # Check another created event fails to validate versions.
        with self.assertRaises(MismatchedOriginatorVersionError):
            aggregate._validate_originator_version(AggregateCreated(originator_id=aggregate.id))

    def test_mutator_errors(self):
        with self.assertRaises(NotImplementedError):
            aggregate_mutator(1, 2)

        # Check the guard condition raises exception.
        with self.assertRaises(MutatorRequiresTypeNotInstance):
            aggregate_mutator(mock.Mock(spec=AggregateCreated), 'not a class')

        # Check the instantiation type error.
        with self.assertRaises(TypeError):
            aggregate_mutator(mock.Mock(spec=AggregateCreated), AggregateRoot)  # needs more than the mock obj has


class EntityCreated(AggregateEvent):
    """
    Published when an entity is created.
    """

    def __init__(self, entity_id, **kwargs):
        super(EntityCreated, self).__init__(entity_id=entity_id, **kwargs)

    @property
    def entity_id(self):
        return self.__dict__['entity_id']


class Example(object):
    """
    Example domain entity.
    """

    def __init__(self, entity_id):
        self._id = entity_id

    @property
    def id(self):
        return self._id


class ExampleAggregateRoot(AggregateRoot):
    def __init__(self, foo='', **kwargs):
        super(ExampleAggregateRoot, self).__init__(**kwargs)
        self._entities = {}
        self._foo = foo

    @attribute
    def foo(self):
        """Event sourced attribute foo."""

    def create_new_entity(self):
        assert not self._is_discarded
        event = EntityCreated(
            entity_id=uuid.uuid4(),
            originator_id=self.id,
            originator_version=self.version,
        )
        self._apply(event)
        self._pending_events.append(event)

    def count_entities(self):
        return len(self._entities)

    @staticmethod
    def _mutator(event, initial):
        return example_aggregate_mutator(event, initial)


@singledispatch
def example_aggregate_mutator(event, self):
    return aggregate_mutator(event, self)


@aggregate_mutator.register(EntityCreated)
def entity_created_mutator(event, self):
    assert not self._is_discarded
    entity = Example(entity_id=event.entity_id)
    self._entities[entity.id] = entity
    self._version += 1
    self._last_modified_on = event.timestamp
    return self


class ExampleDDDApplication(object):
    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                session=datastore.db_session,
                active_record_class=SqlIntegerSequencedItem,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                SequencedItem,
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version',
            )
        )
        self.aggregate_repository = EventSourcedRepository(
            event_store=self.event_store,
            mutator=ExampleAggregateRoot.mutate,
        )
        self.persistence_policy = PersistencePolicy(self.event_store, event_type=AggregateEvent)

    def create_example_aggregate(self):
        """
        Factory method, creates and returns a new example aggregate root object.

        :rtype: ExampleAggregateRoot 
        """
        event = AggregateCreated(originator_id=uuid.uuid4())
        aggregate = ExampleAggregateRoot.mutate(event=event)
        aggregate._pending_events.append(event)
        return aggregate

    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
