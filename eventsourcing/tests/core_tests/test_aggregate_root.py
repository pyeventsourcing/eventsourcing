import uuid
from typing import Dict, Generic, Optional, cast
from unittest.case import TestCase
from uuid import UUID

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.decorators import attribute, subclassevents
from eventsourcing.domain.model.events import DomainEvent, assert_event_handlers_empty
from eventsourcing.exceptions import EventHashError, HeadHashError
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.infrastructure.sqlalchemy.records import IntegerSequencedNoIDRecord
from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_record_manager import (
    SQLAlchemyRecordManagerTestCase,
)
from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.whitehead import TEntity


class TestAggregateRootEvent(TestCase):
    def test_validate_aggregate_events(self):
        event1 = AggregateRoot.Created(
            originator_version=0,
            originator_id="1",
            originator_topic=get_topic(AggregateRoot),
        )
        event1.__check_hash__()

        # Chain another event.
        event2 = AggregateRoot.AttributeChanged(
            originator_version=1,
            originator_id="1",
            __previous_hash__=event1.__event_hash__,
        )
        event2.__check_hash__()

        # Chain another event.
        event3 = AggregateRoot.AttributeChanged(
            originator_version=2,
            originator_id="1",
            __previous_hash__=event2.__event_hash__,
        )
        event3.__check_hash__()

    def test_event_hash_error(self):
        event1 = AggregateRoot.Created(
            originator_version=0,
            originator_id="1",
            originator_topic=get_topic(AggregateRoot),
        )
        event1.__check_hash__()

        # Break the hash.
        event1.__dict__["event_hash"] = "damage"
        with self.assertRaises(EventHashError):
            event1.__check_hash__()


class TestExampleAggregateRoot(SQLAlchemyRecordManagerTestCase):
    def setUp(self) -> None:
        assert_event_handlers_empty()
        super(TestExampleAggregateRoot, self).setUp()
        self.app: ExampleDDDApplication = ExampleDDDApplication(self.datastore)

    def tearDown(self) -> None:
        self.app.close()
        super(TestExampleAggregateRoot, self).tearDown()
        assert_event_handlers_empty()

    def test_example_aggregate_event_classes(self):
        self.assertIn("Event", ExampleAggregateRoot.__dict__)
        self.assertIn("Created", ExampleAggregateRoot.__dict__)
        self.assertIn("Discarded", ExampleAggregateRoot.__dict__)
        self.assertIn("AttributeChanged", ExampleAggregateRoot.__dict__)

        self.assertEqual(ExampleAggregateRoot.Event.__name__, "Event")
        self.assertEqual(
            ExampleAggregateRoot.Event.__qualname__, "ExampleAggregateRoot.Event"
        )
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#ExampleAggregateRoot.Event"
        self.assertEqual(get_topic(ExampleAggregateRoot.Event), topic)
        self.assertEqual(resolve_topic(topic), ExampleAggregateRoot.Event)

        self.assertEqual(ExampleAggregateRoot.Created.__name__, "Created")
        self.assertEqual(
            ExampleAggregateRoot.Created.__qualname__, "ExampleAggregateRoot.Created"
        )
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#ExampleAggregateRoot.Created"
        self.assertEqual(get_topic(ExampleAggregateRoot.Created), topic)
        self.assertEqual(resolve_topic(topic), ExampleAggregateRoot.Created)
        self.assertTrue(
            issubclass(ExampleAggregateRoot.Created, ExampleAggregateRoot.Event)
        )

        self.assertEqual(ExampleAggregateRoot.Discarded.__name__, "Discarded")
        self.assertEqual(
            ExampleAggregateRoot.Discarded.__qualname__,
            "ExampleAggregateRoot.Discarded",
        )
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#ExampleAggregateRoot.Discarded"
        self.assertEqual(get_topic(ExampleAggregateRoot.Discarded), topic)
        self.assertEqual(resolve_topic(topic), ExampleAggregateRoot.Discarded)
        self.assertTrue(
            issubclass(ExampleAggregateRoot.Discarded, ExampleAggregateRoot.Event)
        )

        self.assertEqual(ExampleAggregateRoot.ExampleCreated.__name__, "ExampleCreated")
        self.assertEqual(
            ExampleAggregateRoot.ExampleCreated.__qualname__,
            "ExampleAggregateRoot.ExampleCreated",
        )
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#ExampleAggregateRoot.ExampleCreated"
        self.assertEqual(get_topic(ExampleAggregateRoot.ExampleCreated), topic)
        self.assertEqual(resolve_topic(topic), ExampleAggregateRoot.ExampleCreated)
        self.assertTrue(
            issubclass(ExampleAggregateRoot.ExampleCreated, ExampleAggregateRoot.Event)
        )

    def test_aggregate1_event_classes(self):
        self.assertIn("Event", Aggregate1.__dict__)
        self.assertIn("Created", Aggregate1.__dict__)
        self.assertIn("Discarded", Aggregate1.__dict__)
        self.assertIn("AttributeChanged", Aggregate1.__dict__)

        self.assertEqual(Aggregate1.Event.__name__, "Event")
        self.assertEqual(Aggregate1.Event.__qualname__, "Aggregate1.Event")
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate1.Event"
        self.assertEqual(get_topic(Aggregate1.Event), topic)
        self.assertEqual(resolve_topic(topic), Aggregate1.Event)

        self.assertEqual(Aggregate1.Created.__name__, "Created")
        self.assertEqual(Aggregate1.Created.__qualname__, "Aggregate1.Created")
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate1.Created"
        self.assertEqual(get_topic(Aggregate1.Created), topic)
        self.assertEqual(resolve_topic(topic), Aggregate1.Created)
        self.assertTrue(issubclass(Aggregate1.Created, Aggregate1.Event))

        self.assertEqual(Aggregate1.Discarded.__name__, "Discarded")
        self.assertEqual(Aggregate1.Discarded.__qualname__, "Aggregate1.Discarded")
        topic = (
            "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate1" ".Discarded"
        )
        self.assertEqual(get_topic(Aggregate1.Discarded), topic)
        self.assertEqual(resolve_topic(topic), Aggregate1.Discarded)
        self.assertTrue(issubclass(Aggregate1.Discarded, Aggregate1.Event))

        self.assertEqual(Aggregate1.ExampleCreated.__name__, "ExampleCreated")
        self.assertEqual(
            Aggregate1.ExampleCreated.__qualname__, "Aggregate1.ExampleCreated"
        )
        topic = (
            "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate1"
            ".ExampleCreated"
        )
        self.assertEqual(get_topic(Aggregate1.ExampleCreated), topic)
        self.assertEqual(resolve_topic(topic), Aggregate1.ExampleCreated)
        self.assertTrue(issubclass(Aggregate1.ExampleCreated, Aggregate1.Event))
        self.assertTrue(issubclass(Aggregate1.SomethingElseOccurred, Aggregate1.Event))

    def test_aggregate2_event_classes(self):
        self.assertIn("Event", Aggregate2.__dict__)
        self.assertIn("Created", Aggregate2.__dict__)
        self.assertIn("Discarded", Aggregate2.__dict__)
        self.assertIn("AttributeChanged", Aggregate2.__dict__)

        self.assertEqual(Aggregate2.Event.__name__, "Event")
        self.assertEqual(Aggregate2.Event.__qualname__, "Aggregate2.Event")
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate2.Event"
        self.assertEqual(get_topic(Aggregate2.Event), topic)
        self.assertEqual(resolve_topic(topic), Aggregate2.Event)

        self.assertEqual(Aggregate2.Created.__name__, "Created")
        self.assertEqual(Aggregate2.Created.__qualname__, "Aggregate2.Created")
        topic = "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate2.Created"
        self.assertEqual(get_topic(Aggregate2.Created), topic)
        self.assertEqual(resolve_topic(topic), Aggregate2.Created)
        self.assertTrue(issubclass(Aggregate2.Created, Aggregate2.Event))

        self.assertEqual(Aggregate2.Discarded.__name__, "Discarded")
        self.assertEqual(Aggregate2.Discarded.__qualname__, "Aggregate2.Discarded")
        topic = (
            "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate2" ".Discarded"
        )
        self.assertEqual(get_topic(Aggregate2.Discarded), topic)
        self.assertEqual(resolve_topic(topic), Aggregate2.Discarded)
        self.assertTrue(issubclass(Aggregate2.Discarded, Aggregate2.Event))

        self.assertEqual(Aggregate2.ExampleCreated.__name__, "ExampleCreated")
        self.assertEqual(
            Aggregate2.ExampleCreated.__qualname__, "Aggregate2.ExampleCreated"
        )
        topic = (
            "eventsourcing.tests.core_tests.test_aggregate_root#Aggregate2"
            ".ExampleCreated"
        )
        self.assertEqual(get_topic(Aggregate2.ExampleCreated), topic)
        self.assertEqual(resolve_topic(topic), Aggregate2.ExampleCreated)
        self.assertTrue(issubclass(Aggregate2.ExampleCreated, Aggregate2.Event))

    def test_aggregate3_lifecycle(self):
        # type: () -> None

        # Create a new aggregate.
        aggregate = self.app.create_aggregate3()

        self.assertIsInstance(aggregate, Aggregate3)

    def test_aggregate1_lifecycle(self):
        # type: () -> None

        # Create a new aggregate.
        aggregate = self.app.create_aggregate1()

        self.assertIsInstance(aggregate, Aggregate1)

        # Check it's got a head hash.
        self.assertTrue(aggregate.__head__)
        last_next_hash = aggregate.__head__

        # Check it does not exist in the repository.
        self.assertNotIn(aggregate.id, self.app.repository)

        # Save the aggregate.
        aggregate.__save__()

        # Check it now exists in the repository.
        self.assertIn(aggregate.id, self.app.repository)

        # Change an attribute of the aggregate root entity.
        self.assertNotEqual(aggregate.foo, "bar")
        aggregate.foo = "bar"
        self.assertEqual(aggregate.foo, "bar")

        # Check the head hash has changed.
        self.assertNotEqual(aggregate.__head__, last_next_hash)
        last_next_hash = aggregate.__head__

        self.assertIn(aggregate.id, self.app.repository)

        self.assertNotEqual(self.app.repository[aggregate.id].foo, "bar")
        aggregate.__save__()
        self.assertEqual(self.app.repository[aggregate.id].foo, "bar")

        # Check the aggregate has zero entities.
        self.assertEqual(aggregate.count_examples(), 0)

        # Check the aggregate has zero entities.
        self.assertEqual(aggregate.count_examples(), 0)

        # Ask the aggregate to create an entity within itself.
        aggregate.create_new_example()

        # Check the aggregate has one entity.
        self.assertEqual(aggregate.count_examples(), 1)

        # Check the aggregate in the repo still has zero entities.
        self.assertEqual(
            self.app.repository[aggregate.id].count_examples(), 0
        )

        # Check the head hash has changed.
        self.assertNotEqual(aggregate.__head__, last_next_hash)
        last_next_hash = aggregate.__head__

        # Call save().
        aggregate.__save__()

        # Check the aggregate in the repo now has one entity.
        self.assertEqual(
            self.app.repository[aggregate.id].count_examples(), 1
        )

        # Create two more entities within the aggregate.
        aggregate.create_new_example()
        aggregate.create_new_example()

        # Save both "entity created" events in one atomic transaction.
        aggregate.__save__()

        # Check the aggregate in the repo now has three entities.
        self.assertEqual(
            self.app.repository[aggregate.id].count_examples(), 3
        )

        # Discard the aggregate, calls save().
        aggregate.__discard__()
        aggregate.__save__()

        # Check the next hash has changed.
        self.assertNotEqual(aggregate.__head__, last_next_hash)

        # Check the aggregate no longer exists in the repo.
        self.assertNotIn(aggregate.id, self.app.repository)

    def test_both_types(self):
        # Create a new aggregate.
        aggregate1 = self.app.create_aggregate1()
        aggregate2 = self.app.create_aggregate2()

        aggregate1.__save__()
        aggregate2.__save__()

        self.assertIsInstance(aggregate1, Aggregate1)
        self.assertIsInstance(aggregate2, Aggregate2)

        self.assertEqual(aggregate1.foo, "")
        self.assertEqual(aggregate2.foo, "")

        aggregate1.foo = "bar"
        aggregate2.foo = "baz"

        aggregate1.__save__()
        aggregate2.__save__()

        aggregate1 = self.app.repository[aggregate1.id]
        aggregate2 = self.app.repository[aggregate2.id]

        self.assertIsInstance(aggregate1, Aggregate1)
        self.assertIsInstance(aggregate2, Aggregate2)

        self.assertEqual(aggregate1.foo, "bar")
        self.assertEqual(aggregate2.foo, "baz")

        aggregate1.__discard__()
        aggregate1.__save__()
        self.assertFalse(aggregate1.id in self.app.repository)
        self.assertTrue(aggregate2.id in self.app.repository)

    def test_validate_previous_hash_error(self):
        # Check event has valid originator head.
        aggregate = Aggregate1(id="1", foo="bar", __created_on__=0, __version__=0)
        event = Aggregate1.AttributeChanged(
            name="foo",
            value="bar",
            originator_id="1",
            originator_version=1,
            __previous_hash__=aggregate.__head__,
        )
        event.__check_obj__(aggregate)

        # Check OriginatorHeadError is raised if the originator head is wrong.
        event.__dict__["__previous_hash__"] += "damage"
        with self.assertRaises(HeadHashError):
            event.__check_obj__(aggregate)


@subclassevents
class ExampleAggregateRoot(AggregateRoot):
    def __init__(self, foo="", **kwargs):
        super(ExampleAggregateRoot, self).__init__(**kwargs)
        self._entities: Dict[UUID, Example] = {}
        self._foo = foo

    @attribute
    def foo(self):
        """Simple event sourced attribute called 'foo'."""

    def create_new_example(self):
        assert not self.__is_discarded__
        self.__trigger_event__(self.ExampleCreated, entity_id=uuid.uuid4())

    def count_examples(self):
        return len(self._entities)

    class ExampleCreated(DomainEvent[TEntity]):
        """Published when an example entity is created within the aggregate."""

        def __init__(self, entity_id, **kwargs):
            super().__init__(entity_id=entity_id, **kwargs)

        @property
        def entity_id(self):
            return self.__dict__["entity_id"]

        def __mutate__(self, obj: Optional[TEntity]) -> Optional[TEntity]:
            obj = super().__mutate__(obj)
            if obj:
                assert isinstance(obj, ExampleAggregateRoot)
                entity = Example(entity_id=self.entity_id)
                obj._entities[entity.id] = entity
            return obj

    class SomethingElseOccurred(DomainEvent):
        pass


@subclassevents
class Aggregate1(ExampleAggregateRoot):
    pass


class Aggregate2(ExampleAggregateRoot):
    __subclassevents__ = True


class Aggregate3(Aggregate2):
    pass


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


class ExampleDDDApplication(Generic[TEntity]):
    def __init__(self, datastore):
        event_store = EventStore(
            record_manager=SQLAlchemyRecordManager(
                session=datastore.session, record_class=IntegerSequencedNoIDRecord
            ),
            event_mapper=SequencedItemMapper(
                sequence_id_attr_name="originator_id",
                position_attr_name="originator_version",
            ),
        )
        self.repository = EventSourcedRepository(event_store=event_store)
        self.persistence_policy = PersistencePolicy(
            persist_event_type=ExampleAggregateRoot.Event, event_store=event_store
        )

    def create_aggregate1(self) -> Aggregate1:
        """
        Factory method, creates and returns a new aggregate1 root entity.
        """
        a: Aggregate1 = Aggregate1.__create__()
        return a

    def create_aggregate2(self) -> Aggregate2:
        """
        Factory method, creates and returns a new aggregate1 root entity.
        """
        a: Aggregate2 = Aggregate2.__create__()
        return a

    def create_aggregate3(self) -> Aggregate3:
        """
        Factory method, creates and returns a new aggregate1 root entity.
        """
        a = Aggregate3.__create__()
        return a

    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
