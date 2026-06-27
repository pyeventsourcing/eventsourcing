from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar
from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import (
    Aggregate,
    AggregateCreated,
    AggregateEvent,
    BaseAggregate,
    OriginatorIDError,
    OriginatorVersionError,
    ProgrammingError,
    event,
)
from eventsourcing.utils import get_method_name

X = int  # pyright: ignore [reportAssignmentType]

try:

    class X(BaseAggregate):  # type: ignore[no-redef]
        pass

except ProgrammingError:
    pass
else:
    msg = "eventsourcing.module isn't checking for redefined names"
    raise AssertionError(msg)


class TestBaseAggregate(TestCase):
    def test_base_aggregate_class_cannot_be_instantiated_directly(self) -> None:
        with self.assertRaises(TypeError) as cm:
            BaseAggregate()

        self.assertIn(
            "Please define or use subclasses of BaseAggregate",
            str(cm.exception),
        )

    def test_aggregate_class_can_be_instantiated_directly(self) -> None:
        # Create an aggregate by calling the class.
        a = Aggregate()
        self.assertIsInstance(a, Aggregate)
        self.assertIsInstance(a, BaseAggregate)
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertIsInstance(a.pending_events[0], Aggregate.Event)
        self.assertIsInstance(a.pending_events[0], Aggregate.Created)
        self.assertEqual(a.pending_events[0].originator_id, a.id)
        self.assertEqual(a.pending_events[0].originator_version, 1)

        aggregate_id = a.id

        # Trigger a subsequent event.
        a.trigger_event(Aggregate.Event)
        self.assertIsInstance(a.id, UUID)
        self.assertEqual(a.id, aggregate_id)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 2)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertLess(a.created_on, a.modified_on)
        self.assertIsInstance(a.pending_events[1], Aggregate.Event)
        self.assertNotIsInstance(a.pending_events[1], Aggregate.Created)
        self.assertEqual(a.pending_events[1].originator_id, a.id)
        self.assertEqual(a.pending_events[1].originator_version, 2)

        self.assertEqual(
            repr(a),
            f"Aggregate(id={a.id!r}, version=2, "
            f"created_on={a.created_on!r}, "
            f"modified_on={a.modified_on!r})",
        )

        # Create an aggregate by calling the _create() method.
        a = Aggregate._create(event_class=Aggregate.Created)
        self.assertIsInstance(a, Aggregate)
        self.assertIsInstance(a, BaseAggregate)
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertIsInstance(a.pending_events[0], Aggregate.Event)
        self.assertIsInstance(a.pending_events[0], Aggregate.Created)
        self.assertEqual(a.pending_events[0].originator_id, a.id)
        self.assertEqual(a.pending_events[0].originator_version, 1)

        # Raises TypeError if event class can't be constructed.
        with self.assertRaises(TypeError) as cm:
            a = Aggregate._create(event_class=Aggregate.Event)  # type: ignore[arg-type]

        self.assertTrue(
            str(cm.exception).startswith(
                f"Unable to construct 'Aggregate.Event' event: "
                f"{get_method_name(Aggregate.Event.__init__)}() got an "
                "unexpected keyword argument 'originator_topic'",
            ),
            str(cm.exception),
        )

        # Raises type error if event class can't be constructed.
        with self.assertRaises(TypeError) as cm:
            a.trigger_event(Aggregate.Event, b=23)

        self.assertEqual(
            str(cm.exception),
            "Can't construct event <class 'eventsourcing.domain.Aggregate.Event'>: "
            f"{get_method_name(Aggregate.Event.__init__)}() got an unexpected keyword "
            f"argument 'b'",
        )

    def test_events_can_reconstruct_aggregate(self) -> None:
        a = Aggregate()
        a.trigger_event(Aggregate.Event)

        # Collect events and reconstruct copy.
        a_events = a.collect_events()
        self.assertEqual(len(a_events), 2)

        a_copy: Aggregate | None = None
        for e in a_events:
            a_copy = e.mutate(a_copy)
        self.assertEqual(a_copy, a)

        # Check we can't mix events from aggregates.
        b = Aggregate()
        b.trigger_event(Aggregate.Event)
        b_events = b.collect_events()

        b_copy = b_events[0].mutate(None)
        with self.assertRaises(OriginatorIDError):
            a_events[1].mutate(b_copy)

        # Check we can't mutate an event twice.
        b_events[1].mutate(b_copy)
        with self.assertRaises(OriginatorVersionError):
            b_events[1].mutate(b_copy)

    def test_raises_programming_error_if_name_already_defined(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class X(BaseAggregate):
                pass

        self.assertTrue(
            str(cm.exception).startswith("Name 'X'"),
            str(cm.exception),
        )
        self.assertIn("already defined", str(cm.exception))

    def test_cant_identify_suitable_base_class_for_created_event_class(self) -> None:
        class A(BaseAggregate):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

        with self.assertRaises(TypeError) as cm:
            A()

        self.assertEqual(
            "No \"created\" event classes defined on class 'A'.",
            str(cm.exception),
        )

    def test_subclass_can_be_instantiated_directly(self) -> None:
        class A(Aggregate):
            pass

        a = A()

        self.assertIsInstance(a, A)
        self.assertIsInstance(a, BaseAggregate)
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertIsInstance(a.pending_events[0], A.Event)
        self.assertIsInstance(a.pending_events[0], A.Created)
        self.assertEqual(a.pending_events[0].originator_id, a.id)
        self.assertEqual(a.pending_events[0].originator_version, 1)

        aggregate_id = a.id

        # Trigger a subsequent event.
        a.trigger_event(A.Event)
        self.assertIsInstance(a.id, UUID)
        self.assertEqual(a.id, aggregate_id)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 2)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertLess(a.created_on, a.modified_on)
        self.assertIsInstance(a.pending_events[1], A.Event)
        self.assertNotIsInstance(a.pending_events[1], A.Created)
        self.assertEqual(a.pending_events[1].originator_id, a.id)
        self.assertEqual(a.pending_events[1].originator_version, 2)

    def test_annotations_mention_id_no_default(self) -> None:
        class A(Aggregate):
            id: UUID  # pyright: ignore [reportIncompatibleMethodOverride]

        a_id = uuid4()
        a = A(id=a_id)  # type: ignore [call-arg]
        self.assertEqual(a.id, a_id)

        with self.assertRaises(TypeError) as cm:
            A()

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(A.__init__)}() missing "
            f"1 required positional argument: 'id'",
        )

    def test_annotations_mention_id_has_default(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class A(BaseAggregate):
                id: UUID = field(  # pyright: ignore [reportIncompatibleMethodOverride]
                    default_factory=uuid4,
                )

        self.assertEqual(
            str(cm.exception), "Setting attribute 'id' on class 'A' is not allowed"
        )

    def test_non_id_annotations(self) -> None:
        # Required argument in __init__ method.
        class A(Aggregate):
            name: str

        a = A(name="foo")  # type: ignore [call-arg]
        self.assertEqual(a.name, "foo")

        with self.assertRaises(TypeError) as cm:
            A()

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(A.__init__)}() "
            f"missing 1 required positional argument: 'name'",
        )

        class B(Aggregate):
            name: str = field(default="bar")

        # Optional argument in __init__ method.
        b = B()
        self.assertEqual(b.name, "bar")
        b = B(name="foo")  # type: ignore [call-arg]
        self.assertEqual(b.name, "foo")

        # Not included in __init__ method.
        class C(Aggregate):
            name: str = field(default="bar", init=False)

        with self.assertRaises(TypeError) as cm:
            C(name="foo")  # type: ignore [call-arg]

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(C.__init__)}() "
            "got an unexpected keyword argument 'name'",
        )

    def test_init_mentions_id_no_default(self) -> None:
        class A(Aggregate):
            def __init__(self, id: UUID) -> None:  # noqa: A002
                pass

        a_id = uuid4()
        a = A(id=a_id)
        self.assertEqual(a.id, a_id)

        with self.assertRaises(TypeError) as cm:
            A()  # type: ignore [call-arg]

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(A.__init__)}() missing "
            f"1 required positional argument: 'id'",
        )

    def test_init_mentions_non_id_args_no_default(self) -> None:
        class A(Aggregate):
            def __init__(self, name: str) -> None:
                self.name = name

        a = A(name="foo")
        self.assertEqual(a.name, "foo")

        with self.assertRaises(TypeError) as cm:
            A()  # type: ignore [call-arg]

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(A.__init__)}() missing "
            f"1 required positional argument: 'name'",
        )

        with self.assertRaises(TypeError) as cm:
            A(id="baz")  # type: ignore [call-arg]

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(A.__init__)}() got an unexpected keyword argument 'id'",
        )

    def test_init_mentions_non_id_args_has_default(self) -> None:
        class A(Aggregate):
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")

        a = A(name="foo")
        self.assertEqual(a.name, "foo")

        with self.assertRaises(TypeError) as cm:
            A(id="baz")  # type: ignore [call-arg]

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(A.__init__)}() "
            f"got an unexpected keyword argument 'id'",
        )

    def test_init_has_event_decorator_without_name_or_class(self) -> None:
        with self.assertRaises(TypeError) as cm:

            class A(BaseAggregate):
                @event
                def __init__(self) -> None:
                    pass

        self.assertEqual(
            str(cm.exception),
            "@event decorator on __init__ has neither event name nor class",
        )

    def test_base_event_class_not_defined(self) -> None:
        with self.assertRaises(TypeError) as cm:

            class A(BaseAggregate):
                class SubsequentEvent(AggregateEvent):
                    pass

        self.assertIn("Base event class 'Event' not defined", str(cm.exception))

    def test_init_has_event_decorator_with_class_wrong_type(self) -> None:
        with self.assertRaises(TypeError) as cm:

            class A(BaseAggregate):
                class Event(AggregateEvent):
                    pass

                class Started(AggregateEvent):
                    pass

                @event(Started)
                def __init__(self, name: str = "bar") -> None:
                    self.name = name

        self.assertIn("<locals>.A.Started", str(cm.exception))
        self.assertIn("does not derive from CanInitAggregate", str(cm.exception))

    def test_raises_not_implemented_error_if_create_id_not_implemented(self) -> None:
        class A(BaseAggregate):
            class Event(AggregateEvent):
                pass

            class Created(Event, AggregateCreated):
                pass

        with self.assertRaises(NotImplementedError) as cm:
            A()

        self.assertIn(
            "Please pass an 'id' arg or define a create_id() method",
            str(cm.exception),
        )

    def test_init_has_event_decorator_with_class_correct_type_mismatched_attrs(
        self,
    ) -> None:
        class A(BaseAggregate):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class Started(AggregateCreated):
                pass

            @event(Started)
            def __init__(self, name: str) -> None:
                self.name = name

        with self.assertRaises(TypeError) as cm:
            A()  # type: ignore [call-arg]

        self.assertEqual(
            str(cm.exception),
            f"{get_method_name(A.__init__)}() missing "
            f"1 required positional argument: 'name'",
        )

    def test_init_has_event_decorator_with_class_matched_attrs_wrong_call(self) -> None:
        class A(BaseAggregate):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class Started(AggregateCreated):
                pass

            @event(Started)
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        with self.assertRaises(TypeError) as cm:
            A()

        self.assertEqual(
            str(cm.exception),
            "Unable to construct 'TestBaseAggregate.test_init_has_event_decorator"
            "_with_class_matched_attrs_wrong_call.<locals>.A.Started' event: "
            f"{get_method_name(A.Started.__init__)}() got "
            f"an unexpected keyword argument 'name'",
        )

    def test_init_has_event_decorator_with_class_matched_attrs_correct_call(
        self,
    ) -> None:

        class A(BaseAggregate):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class Started(AggregateCreated):
                name: str

            @event(Started)
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(a.pending_events[0], A.Started)

    def test_init_has_event_decorator_with_class_defined_above_aggregate_class(
        self,
    ) -> None:
        class Started(AggregateCreated):
            name: str

        class A(BaseAggregate):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            @event(Started)
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(a.pending_events[0], Started)

    def test_init_has_event_decorator_with_class_name(self) -> None:

        class A(Aggregate):
            @event("Started")
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(
            a.pending_events[0],
            A.Started,  # type: ignore[attr-defined]
        )

    def test_class_has_created_event_name(self) -> None:

        class A(Aggregate, created_event_name="Started"):
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(
            a.pending_events[0],
            A.Started,  # type: ignore[attr-defined]
        )

    def test_created_event_name_conflicts_with_decorator_name(self) -> None:

        # This is not okay.
        with self.assertRaises(TypeError) as cm:

            class _A(Aggregate, created_event_name="Began"):
                @event("Started")
                def __init__(self, name: str = "bar") -> None:
                    self.name = name

        self.assertEqual(
            str(cm.exception),
            "Given 'created_event_name' conflicts with decorator on __init__",
        )

        # This is okay.
        class A(Aggregate, created_event_name="Started"):
            @event("Started")
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(
            a.pending_events[0],
            A.Started,  # type: ignore[attr-defined]
        )

    def test_created_event_name_conflicts_with_decorator_class(self) -> None:

        # This is not okay.
        with self.assertRaises(TypeError) as cm:

            class A1(BaseAggregate, created_event_name="Began"):
                @staticmethod
                def create_id() -> UUID:
                    return uuid4()

                class Event(AggregateEvent):
                    pass

                class Started(AggregateCreated):
                    name: str

                @event(Started)
                def __init__(self, name: str = "bar") -> None:
                    self.name = name

        self.assertEqual(
            str(cm.exception),
            "Given 'created_event_name' conflicts with decorator on __init__",
        )

        # This is okay.
        class A2(BaseAggregate, created_event_name="Started"):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class SomethingHappened(AggregateCreated):  # for coverage
                pass

            class Started(AggregateCreated):
                name: str

            @event(Started)
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A2()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(a.pending_events[0], A2.Started)

    def test_created_event_name_matches_defined_class(self) -> None:
        class A(BaseAggregate, created_event_name="Started"):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class Started(AggregateCreated):
                name: str

            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(a.pending_events[0], A.Started)

    def test_created_event_name_without_create_event_base_class(self) -> None:
        with self.assertRaises(TypeError):

            class A1(BaseAggregate, created_event_name="Started"):
                pass

        with self.assertRaises(TypeError):

            class A2(BaseAggregate):
                @event("Started")
                def __init__(self) -> None:
                    pass

    def test_decorator_event_name_matches_defined_class(self) -> None:
        class A(BaseAggregate):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class Started(AggregateCreated):
                name: str

            @event("Started")
            def __init__(self, name: str = "bar") -> None:
                self.name = name

        a = A()
        self.assertEqual(a.name, "bar")
        self.assertIsInstance(a.pending_events[0], A.Started)

    def test_named_created_event_class_inherits_from_super_class_synonym(self) -> None:
        # This is basically what the library's Aggregate class does.
        class A(BaseAggregate):
            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class Started(AggregateCreated):
                pass

            class Began(AggregateCreated):
                pass

            class Registered(AggregateCreated):
                pass

        class B(A, created_event_name="Began"):
            pass

        b = B()
        self.assertIsInstance(b.pending_events[0], B.Began)
        self.assertTrue(issubclass(B.Began, A.Began))

        class C(B):
            pass

        c = C()
        self.assertIsInstance(c.pending_events[0], C.Began)
        self.assertTrue(issubclass(C.Began, B.Began))

    def test_method_decorator_uses_string_but_base_event_not_defined(self) -> None:

        with self.assertRaises(TypeError) as cm:

            class A(BaseAggregate):
                @event("Commanded")
                def command(self) -> None:
                    pass

        self.assertIn("Base event class 'Event' not defined", str(cm.exception))

    def test_original_subclass_relations_are_respected_issue_295(self) -> None:
        # Issue #295 on GitHub.
        # https://github.com/pyeventsourcing/eventsourcing/issues/295
        class A(BaseAggregate):
            class Event(AggregateEvent):
                pass

            class Created(AggregateCreated, Event):
                pass

        # Basically, when we redefine an event in B, it must inherit from
        # the original class, from any redefined event classes on B that are
        # in its bases, and from B's base event class. In this example, B
        # doesn't have its own base event class, so Something and Scheduled
        # are redefined. Unless the hierarchy is preserved, after the class
        # is defined, B.Scheduled will not be a subclass of B.Something.

        # This 'X' just makes sure we are picking up the synonymous B.Created class.
        # TODO: Move this aspect to a separate class...
        class X(AggregateEvent):
            pass

        class B(A):
            class Something(A.Event):
                pass

            class Scheduled(Something):
                pass

            class Created(Something, X):
                pass

            self.assertTrue(issubclass(Scheduled, Something))
            self.assertTrue(issubclass(Created, X))
            self.assertTrue(issubclass(Created, Something))

        # Redefined classes should respect original hierarchy.
        self.assertTrue(issubclass(B.Scheduled, B.Something))
        self.assertTrue(issubclass(B.Created, X))
        self.assertTrue(issubclass(B.Created, B.Something))

    def test_original_subclass_relations_are_respected_with_decorators(self) -> None:
        # Issue #295 on GitHub.
        # https://github.com/pyeventsourcing/eventsourcing/issues/295
        class A(BaseAggregate):
            class Event(AggregateEvent):
                pass

            class Created(Event, AggregateCreated):
                pass

        # Basically, when we redefine an event in B, it must inherit from
        # the original class, from any redefined event classes on B that are
        # in its bases, and from B's base event class. In this example, B
        # doesn't have its own base event class, so Something and Scheduled
        # are redefined. Unless the hierarchy is preserved, after the class
        # is defined, B.Scheduled will not be a subclass of B.Something.
        class B(A):
            class Something(A.Event):
                pass

            class Scheduled(Something):
                pass

            class Created(A.Created, Something):
                pass

            # NB: This breaks it. So basically, it seems the MRO
            # breaks if a subclass is used as in a decorator.
            #
            # @event(Something)
            # def meth1(self) -> None:
            #     pass

            @event(Scheduled)
            def meth2(self) -> None:
                pass

            self.assertTrue(issubclass(Scheduled, Something))
            self.assertTrue(issubclass(Created, Something))

        # Redefined classes should respect original hierarchy.
        self.assertTrue(issubclass(B.Scheduled, B.Something))
        self.assertTrue(issubclass(B.Created, B.Something))

    def test_original_subclass_relations_are_respected_with_pydantic_generics(
        self,
    ) -> None:
        # Issue #295 on GitHub.
        # https://github.com/pyeventsourcing/eventsourcing/issues/295

        from pydantic import BaseModel  # noqa: PLC0415

        from eventsourcing.domain import (  # noqa: PLC0415
            BaseAggregate,
            CanInitAggregate,
            CanMutateAggregate,
        )

        class DomainEvent(BaseModel):
            originator_id: UUID
            originator_version: int
            timestamp: datetime

        class A(BaseAggregate):
            class Event(DomainEvent, CanMutateAggregate):
                pass

            class Created(Event, CanInitAggregate):
                originator_topic: str

        class Shared(BaseModel):
            system_id: str

        class ExtendedShared(Shared):
            task_id: str

        SharedId = TypeVar("SharedId", bound=Shared)

        class B(A):
            class Something(A.Event, Generic[SharedId]):
                shared_id: SharedId

            class Else(Something[ExtendedShared]):
                pass

            class Scheduled(Else):
                pass

            self.assertTrue(issubclass(Else, Something))
            self.assertTrue(issubclass(Scheduled, Else))
            self.assertTrue(issubclass(Scheduled, Something))

        # Redefined classes should respect original hierarchy.
        self.assertTrue(issubclass(B.Else, B.Something))
        self.assertTrue(issubclass(B.Scheduled, B.Else))
        self.assertTrue(issubclass(B.Scheduled, B.Something))

    def test_original_subclass_relations_are_respected_with_dataclass_generics(
        self,
    ) -> None:
        # Issue #295 on GitHub.
        # https://github.com/pyeventsourcing/eventsourcing/issues/295

        from eventsourcing.domain import (  # noqa: PLC0415
            BaseAggregate,
            CanInitAggregate,
            CanMutateAggregate,
        )

        @dataclass(frozen=True)
        class DomainEvent:
            originator_id: UUID
            originator_version: int
            timestamp: datetime

        class A(BaseAggregate):
            @dataclass(frozen=True)
            class Event(DomainEvent, CanMutateAggregate):
                pass

            @dataclass(frozen=True)
            class Created(Event, CanInitAggregate):
                originator_topic: str

        @dataclass(frozen=True)
        class Shared:
            system_id: str

        @dataclass(frozen=True)
        class ExtendedShared(Shared):
            task_id: str

        SharedId = TypeVar("SharedId", bound=Shared)

        class B(A):
            @dataclass(frozen=True)
            class Something(A.Event, Generic[SharedId]):
                shared_id: SharedId

            @dataclass(frozen=True)
            class Else(Something[ExtendedShared]):
                pass

            class Scheduled(Else):
                pass

            class Created(A.Created, Something[ExtendedShared]):
                pass

            self.assertTrue(issubclass(Else, Something))
            self.assertTrue(issubclass(Scheduled, Else))
            self.assertTrue(issubclass(Scheduled, Something))
            self.assertTrue(issubclass(Created, Something))

        # Redefined classes should respect original hierarchy.
        self.assertTrue(issubclass(B.Else, B.Something))
        self.assertTrue(issubclass(B.Scheduled, B.Else))
        self.assertTrue(issubclass(B.Scheduled, B.Something))
        self.assertTrue(issubclass(B.Created, B.Something))
