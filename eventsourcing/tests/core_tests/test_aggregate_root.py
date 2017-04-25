import uuid

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.aggregate_root import AggregateRoot
from eventsourcing.domain.model.entity import Created, attribute, entity_mutator, singledispatch
from eventsourcing.domain.model.events import TimestampedVersionedEntityEvent
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, \
    SqlIntegerSequencedItem
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
    WithSQLAlchemyActiveRecordStrategies


class TestExampleAggregateRoot(WithSQLAlchemyActiveRecordStrategies):
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
        self.assertEqual(aggregate.count_examples(), 0)

        # Check the aggregate has zero entities.
        self.assertEqual(aggregate.count_examples(), 0)

        # Ask the aggregate to create an entity within itself.
        aggregate.create_new_example()

        # Check the aggregate has one entity.
        self.assertEqual(aggregate.count_examples(), 1)

        # Check the aggregate in the repo still has zero entities.
        self.assertEqual(self.app.aggregate_repository[aggregate.id].count_examples(), 0)

        # Call save().
        aggregate.save()

        # Check the aggregate in the repo now has one entity.
        self.assertEqual(self.app.aggregate_repository[aggregate.id].count_examples(), 1)

        # Create two more entities within the aggregate.
        aggregate.create_new_example()
        aggregate.create_new_example()

        # Save both "entity created" events in one atomic transaction.
        aggregate.save()

        # Check the aggregate in the repo now has three entities.
        self.assertEqual(self.app.aggregate_repository[aggregate.id].count_examples(), 3)

        # Discard the aggregate, but don't call save() yet.
        aggregate.discard()

        # Check the aggregate still exists in the repo.
        self.assertIn(aggregate.id, self.app.aggregate_repository)

        # Call save().
        aggregate.save()

        # Check the aggregate no longer exists in the repo.
        self.assertNotIn(aggregate.id, self.app.aggregate_repository)


class ExampleAggregateRoot(AggregateRoot):
    def __init__(self, foo='', **kwargs):
        super(ExampleAggregateRoot, self).__init__(**kwargs)
        self._entities = {}
        self._foo = foo

    @attribute
    def foo(self):
        """Event sourced attribute foo."""

    def create_new_example(self):
        assert not self._is_discarded
        event = ExampleCreated(
            entity_id=uuid.uuid4(),
            originator_id=self.id,
            originator_version=self.version,
        )
        self._apply(event)
        self._publish(event)

    def count_examples(self):
        return len(self._entities)

    @staticmethod
    def _mutator(event, initial):
        return example_aggregate_mutator(event, initial)


class ExampleCreated(TimestampedVersionedEntityEvent):
    """
    Published when an entity is created by an aggregate.
    """

    def __init__(self, entity_id, **kwargs):
        super(ExampleCreated, self).__init__(entity_id=entity_id, **kwargs)

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


@singledispatch
def example_aggregate_mutator(event, self):
    return entity_mutator(event, self)


@example_aggregate_mutator.register(ExampleCreated)
def entity_created_mutator(event, self):
    assert not self._is_discarded
    entity = Example(entity_id=event.entity_id)
    self._entities[entity.id] = entity
    self._version += 1
    self._last_modified_on = event.timestamp
    return self


class ExampleDDDApplication(object):
    def __init__(self, datastore):
        event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                session=datastore.db_session,
                active_record_class=SqlIntegerSequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version',
            )
        )
        self.aggregate_repository = EventSourcedRepository(
            mutator=ExampleAggregateRoot.mutate,
            event_store=event_store,
        )
        self.persistence_policy = PersistencePolicy(
            event_type=TimestampedVersionedEntityEvent,
            event_store=event_store,
        )

    def create_example_aggregate(self):
        """
        Factory method, creates and returns a new example aggregate root object.

        :rtype: ExampleAggregateRoot 
        """
        event = Created(originator_id=uuid.uuid4())
        aggregate = ExampleAggregateRoot.mutate(event=event)
        aggregate._pending_events.append(event)
        return aggregate

    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
