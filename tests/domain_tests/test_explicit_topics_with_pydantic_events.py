from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from unittest import TestCase
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from eventsourcing.domain import (
    BaseAggregate,
    CanInitAggregate,
    CanMutateAggregate,
    MetaAggregate,
    ProgrammingError,
    datetime_now_with_tzinfo,
    get_metadata_from_context,
)
from eventsourcing.utils import (
    clear_topic_cache,
    get_topic,
    register_topic,
)


class Immutable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DomainEvent(Immutable):
    originator_id: UUID
    originator_version: int
    timestamp: datetime = Field(default_factory=datetime_now_with_tzinfo)
    metadata: dict[str, str] = Field(default_factory=get_metadata_from_context)


# Making the aggregate uncallable has nothing to do with explicit topics.
class UncallableMetaAggregate(MetaAggregate[Any]):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        msg = "Calling the aggregate class is prohibited."
        raise ProgrammingError(msg)


class CreatedEvent(DomainEvent, CanInitAggregate[UUID]):
    originator_topic: str


class Aggregate(BaseAggregate[UUID], metaclass=UncallableMetaAggregate):
    TOPIC = "PydanticAggregate"

    @staticmethod
    def create_id() -> UUID:
        return uuid4()

    class Event(DomainEvent, CanMutateAggregate[UUID]):
        pass


class TestExplicitTopics(TestCase):
    def setUp(self) -> None:
        clear_topic_cache()
        register_topic(get_topic(Aggregate), Aggregate)
        register_topic(get_topic(Aggregate.Event), Aggregate.Event)

    def test_create(self) -> None:
        # Topic not defined on CreatedEvent.
        with self.assertRaises(ProgrammingError) as cm:
            Aggregate._create(event_class=CreatedEvent)

        self.assertIn(
            "topic not defined",
            str(cm.exception),
            str(cm.exception),
        )

        # Has topic but topic not registered.
        class BadCreated(CreatedEvent):
            TOPIC: ClassVar[str] = "BadCreated"

        with self.assertRaises(ProgrammingError) as cm:
            Aggregate._create(event_class=BadCreated)

        # Topic resolves to another object.
        register_topic("BadCreated", CreatedEvent)

        with self.assertRaises(ProgrammingError) as cm:
            Aggregate._create(event_class=BadCreated)

        # This is okay.
        class Created(CreatedEvent):
            TOPIC: ClassVar[str] = "Created"

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

                class Started(CreatedEvent):
                    pass

        self.assertIn("not defined", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

            class Started(CreatedEvent):
                TOPIC: ClassVar[str] = "MyAggregate2Started"

    def test_aggregate_class_is_uncallable(self) -> None:
        # Can't call Aggregate base class.
        with self.assertRaises(ProgrammingError) as cm:
            Aggregate()

        self.assertIn(
            "Calling the aggregate class is prohibited.",
            str(cm.exception),
        )

        # Can't call MyAggregate subclass.
        class MyAggregate(Aggregate):
            TOPIC = "MyAggregate"

            class Started(CreatedEvent):
                TOPIC: ClassVar[str] = "MyAggregateStarted"

        with self.assertRaises(ProgrammingError) as cm:
            MyAggregate()

        self.assertIn(
            "Calling the aggregate class is prohibited.",
            str(cm.exception),
        )

        # This is okay.
        MyAggregate._create(event_class=MyAggregate.Started)

    def test_raises_if_explicit_topic_not_on_subsequent_event(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                TOPIC = "MyAggregate1"

                class Started(CreatedEvent):
                    TOPIC: ClassVar[str] = "MyAggregate1Started"

                class Subsequent(Aggregate.Event):
                    pass

        self.assertIn("not defined", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

            class Started(CreatedEvent):
                TOPIC: ClassVar[str] = "MyAggregate2Started"

            class Subsequent(DomainEvent):
                TOPIC: ClassVar[str] = "MyAggregate2Subsequent"

    def test_raises_if_explicit_topic_reused_on_subsequent_event(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class MyAggregate1(Aggregate):
                TOPIC = "MyAggregate1"

                class Started(CreatedEvent):
                    TOPIC: ClassVar[str] = "MyAggregate1Started"

                class Subsequent(Aggregate.Event):
                    TOPIC: ClassVar[str] = "MyAggregate1Started"

        self.assertIn("already registered", str(cm.exception))

        # This is okay.
        class MyAggregate2(Aggregate):
            TOPIC = "MyAggregate2"

            class Started(CreatedEvent):
                TOPIC: ClassVar[str] = "MyAggregate2Started"

            class Subsequent(DomainEvent):
                TOPIC: ClassVar[str] = "MyAggregate2Subsequent"

    def test_raises_if_base_event_is_triggered(self) -> None:
        # Define an aggregate.
        class MyAggregate(Aggregate):
            TOPIC = "MyAggregate"

            class Started(CreatedEvent):
                TOPIC: ClassVar[str] = "MyAggregateStarted"

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

            class Started(CreatedEvent):
                TOPIC: ClassVar[str] = "MyAggregateStarted"

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
            TOPIC: ClassVar[str] = "AggregateEvent2"

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(AggregateEvent2)

        self.assertIn("not registered", str(cm.exception))

        # Has an explicit topic but registered to another object.
        class AggregateEvent3(Aggregate.Event):
            TOPIC: ClassVar[str] = "AggregateEvent3"

        register_topic(AggregateEvent3.TOPIC, Aggregate.Event)

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(AggregateEvent3)

        self.assertIn("already registered", str(cm.exception))

        # Has an explicit topic and registered to correct.
        class AggregateEvent4(Aggregate.Event):
            TOPIC: ClassVar[str] = "AggregateEvent4"

        register_topic(AggregateEvent4.TOPIC, AggregateEvent4)

        # This is okay.
        a.trigger_event(AggregateEvent4)

    def test_raises_if_domain_event_is_triggered(self) -> None:
        # Define an aggregate.
        class MyAggregate(Aggregate):
            TOPIC = "MyAggregate"

            class Started(CreatedEvent):
                TOPIC: ClassVar[str] = "MyAggregateStarted"

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
            TOPIC: ClassVar[str] = "DomaineEvent2"

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(DomainEvent2)  # type: ignore[arg-type]

        self.assertIn("not registered", str(cm.exception))

        # Has an explicit topic but registered to another object.
        class DomainEvent3(DomainEvent):
            TOPIC: ClassVar[str] = "DomaineEvent3"

        register_topic(DomainEvent3.TOPIC, DomainEvent)

        with self.assertRaises(ProgrammingError) as cm:
            a.trigger_event(DomainEvent3)  # type: ignore[arg-type]

        self.assertIn("already registered", str(cm.exception))

        # Has an explicit topic and registered to correct object
        # but it is still just a domain object.
        class DomainEvent4(DomainEvent):
            TOPIC: ClassVar[str] = "DomaineEvent4"

        register_topic(DomainEvent4.TOPIC, DomainEvent4)

        with self.assertRaises(AttributeError):
            a.trigger_event(DomainEvent4)  # type: ignore[arg-type]
