from __future__ import annotations

from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import (
    AggregateCreated,
    AggregateEvent,
    BaseAggregate,
    DomainEvent,
    ProgrammingError,
    event,
)
from eventsourcing.utils import (
    clear_topic_cache,
    get_topic,
    register_topic,
)


class Aggregate(BaseAggregate):
    TOPIC = "Aggregate"

    @staticmethod
    def create_id() -> UUID:
        return uuid4()

    class Event(AggregateEvent):
        pass


class TestExplicitTopics(TestCase):
    def setUp(self) -> None:
        clear_topic_cache()
        register_topic(get_topic(Aggregate), Aggregate)
        register_topic(get_topic(Aggregate.Event), Aggregate.Event)

    def test_create(self) -> None:
        # Topic not defined on AggregateCreated.
        with self.assertRaises(ProgrammingError) as cm:
            Aggregate._create(event_class=AggregateCreated)

        self.assertIn(
            "topic not defined",
            str(cm.exception),
            str(cm.exception),
        )

        # Has topic but topic not registered.
        class BadCreated(AggregateCreated):
            TOPIC = "BadCreated"

        with self.assertRaises(ProgrammingError) as cm:
            Aggregate._create(event_class=BadCreated)

        # Topic resolves to another object.
        register_topic("BadCreated", AggregateCreated)

        with self.assertRaises(ProgrammingError) as cm:
            Aggregate._create(event_class=BadCreated)

        # This is okay.
        class Created(AggregateCreated):
            TOPIC = "Created"

        register_topic(Created.TOPIC, Created)

        Aggregate._create(event_class=Created)

    def test_raises_if_explicit_topic_not_on_aggregate(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                pass

        self.assertIn("not defined", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

    def test_raises_if_explicit_topic_defined_on_aggregate_already_registered(
        self,
    ) -> None:

        register_topic("MyAggregate1", Aggregate)

        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                TOPIC = "MyAggregate1"

        self.assertIn("already registered", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

    def test_raises_if_explicit_topic_not_on_created_event(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                TOPIC = "MyAggregate1"

                class Started(AggregateCreated):
                    pass

        self.assertIn("not defined", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

            class Started(AggregateCreated):
                TOPIC = "MyAggregate2Started"

    def test_raises_if_explicit_topic_not_on_subsequent_event(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                TOPIC = "MyAggregate1"

                class Started(AggregateCreated):
                    TOPIC = "MyAggregate1Started"

                class Subsequent(Aggregate.Event):
                    pass

        self.assertIn("not defined", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

            class Started(AggregateCreated):
                TOPIC = "MyAggregate2Started"

            class Subsequent(DomainEvent):
                TOPIC = "MyAggregate2Subsequent"

    def test_raises_if_explicit_topic_reused_on_subsequent_event(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                TOPIC = "MyAggregate1"

                class Started(AggregateCreated):
                    TOPIC = "MyAggregate1Started"

                class Subsequent(Aggregate.Event):
                    TOPIC = "MyAggregate1Started"

        self.assertIn("already registered", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

            class Started(AggregateCreated):
                TOPIC = "MyAggregate2Started"

            class Subsequent(DomainEvent):
                TOPIC = "MyAggregate2Subsequent"

    def test_raises_if_base_event_is_triggered(self) -> None:
        # Define an aggregate.
        class MyAggregate(Aggregate):
            TOPIC = "MyAggregate"

            class Started(AggregateCreated):
                TOPIC = "MyAggregateStarted"

        # Construct an aggregate.
        a = Aggregate._create(event_class=MyAggregate.Started)

        # Trigger an Event class.
        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(MyAggregate.Event)

        self.assertIn(
            "Triggering base 'Event' class is prohibited.",
            str(cm.exception),
        )

    def test_raises_if_aggregate_event_is_triggered(self) -> None:
        # Define an aggregate.
        class MyAggregate(Aggregate):
            TOPIC = "MyAggregate"

            class Started(AggregateCreated):
                TOPIC = "MyAggregateStarted"

        # Construct an aggregate.
        a = Aggregate._create(event_class=MyAggregate.Started)

        # Without an explicit topic.
        class AggregateEvent1(Aggregate.Event):
            pass

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(AggregateEvent1)

        self.assertIn("not defined", str(cm.exception))

        # Has an explicit topic but not registered.
        class AggregateEvent2(Aggregate.Event):
            TOPIC = "AggregateEvent2"

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(AggregateEvent2)

        self.assertIn("not registered", str(cm.exception))

        # Has an explicit topic but registered to another object.
        class AggregateEvent3(Aggregate.Event):
            TOPIC = "AggregateEvent3"

        register_topic(AggregateEvent3.TOPIC, Aggregate.Event)

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(AggregateEvent3)

        self.assertIn("already registered", str(cm.exception))

        # Has an explicit topic and registered to correct.
        class AggregateEvent4(Aggregate.Event):
            TOPIC = "AggregateEvent4"

        register_topic(AggregateEvent4.TOPIC, AggregateEvent4)

        # This is okay.
        a.trigger_event(AggregateEvent4)

    def test_raises_if_domain_event_is_triggered(self) -> None:
        # Define an aggregate.
        class MyAggregate(Aggregate):
            TOPIC = "MyAggregate"

            class Started(AggregateCreated):
                TOPIC = "MyAggregateStarted"

        # Construct an aggregate.
        a = Aggregate._create(event_class=MyAggregate.Started)

        # Trigger DomainEvent class.
        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(DomainEvent)  # type: ignore[arg-type]

        self.assertIn("not defined", str(cm.exception))

        # Subclass without an explicit topic.
        class DomainEvent1(DomainEvent):
            pass

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(DomainEvent1)  # type: ignore[arg-type]

        self.assertIn("not defined", str(cm.exception))

        # Has an explicit topic but not registered.
        class DomainEvent2(DomainEvent):
            TOPIC = "DomaineEvent2"

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(DomainEvent2)  # type: ignore[arg-type]

        self.assertIn("not registered", str(cm.exception))

        # Has an explicit topic but registered to another object.
        class DomainEvent3(DomainEvent):
            TOPIC = "DomaineEvent3"

        register_topic(DomainEvent3.TOPIC, DomainEvent)

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(DomainEvent3)  # type: ignore[arg-type]

        self.assertIn("already registered", str(cm.exception))

        # Has an explicit topic and registered to correct object
        # but it is still just a domain object.
        class DomainEvent4(DomainEvent):
            TOPIC = "DomaineEvent4"

        register_topic(DomainEvent4.TOPIC, DomainEvent4)

        with self.assertRaises(AttributeError):
            a.trigger_event(DomainEvent4)  # type: ignore[arg-type]

    def test_raises_if_init_decorator_doesnt_define_topic(self) -> None:
        # Define an aggregate.

        class MyAggregate(Aggregate):
            TOPIC = "MyAggregate"

            class Started(AggregateCreated):
                TOPIC = "MyAggregateStarted"

        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(MyAggregate):
                TOPIC = "MyAggregate1"

                @event("Started")
                def __init__(self) -> None:
                    pass

        self.assertIn("already registered", str(cm.exception))

        class MyAggregate2(MyAggregate):
            TOPIC = "MyAggregate2"

            @event("Started", topic="MyAggregate2Started")
            def __init__(self) -> None:
                pass

        self.assertEqual(
            MyAggregate2.Started.TOPIC,
            "MyAggregate2Started",
        )

    def test_raises_if_method_decorator_doesnt_define_topic(self) -> None:
        # Define an aggregate.

        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                TOPIC = "MyAggregate1"

                class Started(AggregateCreated):
                    TOPIC = "MyAggregate1Started"

                @event("SomethingWasDone")
                def do_something(self) -> None:
                    pass

        self.assertIn("not defined", str(cm.exception))

        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

            class Started(AggregateCreated):
                TOPIC = "MyAggregate2Started"

            @event("SomethingWasDone", topic="MyAggregate2SomethingWasDone")
            def do_something(self) -> None:
                pass

        self.assertEqual(
            MyAggregate2.SomethingWasDone.TOPIC,  # type: ignore[attr-defined]
            "MyAggregate2SomethingWasDone",
        )
