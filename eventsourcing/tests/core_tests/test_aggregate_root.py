import uuid
from unittest.case import TestCase

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.decorators import attribute
from eventsourcing.exceptions import EventHashError, HeadHashError
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import IntegerSequencedNoIDRecord
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import \
    SQLAlchemyRecordManagerTestCase
from eventsourcing.utils.topic import get_topic


class TestAggregateRootEvent(TestCase):
    def test_validate_aggregate_events(self):
        event1 = AggregateRoot.Created(
            originator_version=0,
            originator_id='1',
            originator_topic=get_topic(AggregateRoot)
        )
        event1.__check_hash__()

        # Chain another event.
        event2 = AggregateRoot.AttributeChanged(
            originator_version=1,
            originator_id='1',
            __previous_hash__=event1.__event_hash__
        )
        event2.__check_hash__()

        # Chain another event.
        event3 = AggregateRoot.AttributeChanged(
            originator_version=2,
            originator_id='1',
            __previous_hash__=event2.__event_hash__
        )
        event3.__check_hash__()

    def test_event_hash_error(self):
        event1 = AggregateRoot.Created(
            originator_version=0,
            originator_id='1',
            originator_topic=get_topic(AggregateRoot)
        )
        event1.__check_hash__()

        # Break the hash.
        event1.__dict__['event_hash'] = 'damage'
        with self.assertRaises(EventHashError):
            event1.__check_hash__()


class TestExampleAggregateRoot(SQLAlchemyRecordManagerTestCase):
    def setUp(self):
        super(TestExampleAggregateRoot, self).setUp()
        self.app = ExampleDDDApplication(self.datastore)

    def tearDown(self):
        self.app.close()
        super(TestExampleAggregateRoot, self).tearDown()

    def test_aggregate1_lifecycle(self):
        # Create a new aggregate.
        aggregate = self.app.create_aggregate1()

        self.assertIsInstance(aggregate, Aggregate1)

        # Check it's got a head hash.
        self.assertTrue(aggregate.__head__)
        last_next_hash = aggregate.__head__

        # Check it does not exist in the repository.
        self.assertNotIn(aggregate.id, self.app.aggregate1_repository)

        # Save the aggregate.
        aggregate.__save__()

        # Check it now exists in the repository.
        self.assertIn(aggregate.id, self.app.aggregate1_repository)

        # Change an attribute of the aggregate root entity.
        self.assertNotEqual(aggregate.foo, 'bar')
        aggregate.foo = 'bar'
        self.assertEqual(aggregate.foo, 'bar')

        # Check the head hash has changed.
        self.assertNotEqual(aggregate.__head__, last_next_hash)
        last_next_hash = aggregate.__head__

        self.assertIn(aggregate.id, self.app.aggregate1_repository)

        self.assertNotEqual(self.app.aggregate1_repository[aggregate.id].foo, 'bar')
        aggregate.__save__()
        self.assertEqual(self.app.aggregate1_repository[aggregate.id].foo, 'bar')

        # Check the aggregate has zero entities.
        self.assertEqual(aggregate.count_examples(), 0)

        # Check the aggregate has zero entities.
        self.assertEqual(aggregate.count_examples(), 0)

        # Ask the aggregate to create an entity within itself.
        aggregate.create_new_example()

        # Check the aggregate has one entity.
        self.assertEqual(aggregate.count_examples(), 1)

        # Check the aggregate in the repo still has zero entities.
        self.assertEqual(self.app.aggregate1_repository[aggregate.id].count_examples(), 0)

        # Check the head hash has changed.
        self.assertNotEqual(aggregate.__head__, last_next_hash)
        last_next_hash = aggregate.__head__

        # Call save().
        aggregate.__save__()

        # Check the aggregate in the repo now has one entity.
        self.assertEqual(self.app.aggregate1_repository[aggregate.id].count_examples(), 1)

        # Create two more entities within the aggregate.
        aggregate.create_new_example()
        aggregate.create_new_example()

        # Save both "entity created" events in one atomic transaction.
        aggregate.__save__()

        # Check the aggregate in the repo now has three entities.
        self.assertEqual(self.app.aggregate1_repository[aggregate.id].count_examples(), 3)

        # Discard the aggregate, calls save().
        aggregate.__discard__()
        aggregate.__save__()

        # Check the next hash has changed.
        self.assertNotEqual(aggregate.__head__, last_next_hash)

        # Check the aggregate no longer exists in the repo.
        self.assertNotIn(aggregate.id, self.app.aggregate1_repository)

    def test_both_types(self):
        # Create a new aggregate.
        aggregate1 = self.app.create_aggregate1()
        aggregate2 = self.app.create_aggregate2()

        aggregate1.__save__()
        aggregate2.__save__()

        self.assertIsInstance(aggregate1, Aggregate1)
        self.assertIsInstance(aggregate2, Aggregate2)

        self.assertEqual(aggregate1.foo, '')
        self.assertEqual(aggregate2.foo, '')

        aggregate1.foo = 'bar'
        aggregate2.foo = 'baz'

        aggregate1.__save__()
        aggregate2.__save__()

        aggregate1 = self.app.aggregate1_repository[aggregate1.id]
        aggregate2 = self.app.aggregate2_repository[aggregate2.id]

        self.assertIsInstance(aggregate1, Aggregate1)
        self.assertIsInstance(aggregate2, Aggregate2)

        self.assertEqual(aggregate1.foo, 'bar')
        self.assertEqual(aggregate2.foo, 'baz')

        aggregate1.__discard__()
        aggregate1.__save__()
        self.assertFalse(aggregate1.id in self.app.aggregate1_repository)
        self.assertTrue(aggregate2.id in self.app.aggregate2_repository)

        # Todo: Somehow avoid all IDs existing in all repositories.
        # - either namespace the UUIDs, with a UUID for each type,
        #     with adjustments to repository and factory methods.
        # - or make sequence type be a thing, with IDs being valid within the type
        #     compound partition key in Cassandra,
        # self.assertFalse(aggregate2.id in self.app.aggregate1_repository)

    def test_validate_previous_hash_error(self):
        # Check event has valid originator head.
        aggregate = Aggregate1(id='1', foo='bar', __created_on__=0, __version__=0)
        event = Aggregate1.AttributeChanged(name='foo', value='bar', originator_id='1',
                                            originator_version=1, __previous_hash__=aggregate.__head__)
        event.__check_obj__(aggregate)

        # Check OriginatorHeadError is raised if the originator head is wrong.
        event.__dict__['__previous_hash__'] += 'damage'
        with self.assertRaises(HeadHashError):
            event.__check_obj__(aggregate)


class ExampleAggregateRoot(AggregateRoot):
    class Event(AggregateRoot.Event):
        """Supertype for events of example aggregates."""

    class Created(Event, AggregateRoot.Created):
        """Published when an ExampleAggregateRoot is created."""

    class AttributeChanged(Event, AggregateRoot.AttributeChanged):
        """Published when an ExampleAggregateRoot is changed."""

    class Discarded(Event, AggregateRoot.Discarded):
        """Published when an ExampleAggregateRoot is discarded."""

    class ExampleCreated(Event):
        """Published when an example entity is created within the aggregate."""

        def __init__(self, entity_id, **kwargs):
            super(ExampleAggregateRoot.ExampleCreated, self).__init__(entity_id=entity_id, **kwargs)

        @property
        def entity_id(self):
            return self.__dict__['entity_id']

        def __mutate__(self, aggregate):
            super(ExampleAggregateRoot.ExampleCreated, self).__mutate__(aggregate)
            entity = Example(entity_id=self.entity_id)
            aggregate._entities[entity.id] = entity
            return aggregate


class Aggregate1(ExampleAggregateRoot):
    def __init__(self, foo='', **kwargs):
        super(Aggregate1, self).__init__(**kwargs)
        self._entities = {}
        self._foo = foo

    @attribute
    def foo(self):
        """Simple event sourced attribute called 'foo'."""

    def create_new_example(self):
        assert not self.__is_discarded__
        self.__trigger_event__(self.ExampleCreated, entity_id=uuid.uuid4())

    def count_examples(self):
        return len(self._entities)


class Aggregate2(ExampleAggregateRoot):
    def __init__(self, foo='', **kwargs):
        super(Aggregate2, self).__init__(**kwargs)
        self._entities = {}
        self._foo = foo

    @attribute
    def foo(self):
        """Simple event sourced attribute called 'foo'."""

    def create_new_example(self):
        assert not self.__is_discarded__
        self.__trigger_event__(self.ExampleCreated, entity_id=uuid.uuid4())

    def count_examples(self):
        return len(self._entities)


class AggregateRepository(EventSourcedRepository):
    pass


class Example(object):
    """
    Example domain entity.
    """

    def __init__(self, entity_id):
        self._id = entity_id

    @property
    def id(self):
        return self._id


class ExampleDDDApplication(object):
    def __init__(self, datastore):
        event_store = EventStore(
            record_manager=SQLAlchemyRecordManager(
                session=datastore.session,
                record_class=IntegerSequencedNoIDRecord,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequence_id_attr_name='originator_id',
                position_attr_name='originator_version',
            )
        )
        # Todo: Remove having two repositories, because they are identical.
        self.aggregate1_repository = AggregateRepository(
            event_store=event_store,
        )
        self.aggregate2_repository = AggregateRepository(
            event_store=event_store,
        )
        self.persistence_policy = PersistencePolicy(
            persist_event_type=ExampleAggregateRoot.Event,
            event_store=event_store,
        )

    def create_aggregate1(self):
        """
        Factory method, creates and returns a new aggregate1 root entity.

        :rtype: Aggregate1
        """
        return Aggregate1.__create__()

    def create_aggregate2(self):
        """
        Factory method, creates and returns a new aggregate1 root entity.

        :rtype: Aggregate2
        """
        return Aggregate2.__create__()

    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
