from typing import Any, cast
from unittest import TestCase

from eventsourcing.dataclasses.application import DataclassApplication
from eventsourcing.dataclasses.immutable import DataclassDecision
from eventsourcing.dataclasses.mutable import DataclassAggregate
from eventsourcing.domain_new import (
    NIL_UUID,
    AbstractDecision,
    Aggregate,
    TDecision,
    WorksWithDecisions,
    event,
)
from eventsourcing.msgspec.immutable import MsgspecDecision
from eventsourcing.msgspec.mutable import MsgspecAggregate
from eventsourcing.pydantic.application import PydanticApplication
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.mutable import PydanticAggregate


class TestWorksWithDecisions(TestCase):
    def test_works_with_decision_type(self) -> None:
        self.assertIsNone(WorksWithDecisions.works_with_decision_type)

        class GenericSubclassMissingTypeArg(WorksWithDecisions):  # type: ignore[type-arg]
            pass

        self.assertIsNone(GenericSubclassMissingTypeArg.works_with_decision_type)

        class GenericSubclass(WorksWithDecisions[TDecision]):
            pass

        self.assertIsNone(GenericSubclass.works_with_decision_type)

        class MyDecision(AbstractDecision):
            def as_dict(self) -> dict[str, Any]:
                return self.__dict__

        with self.assertRaises(TypeError) as cm:
            GenericSubclass._check_decision_type(int)

        self.assertIn("has no decision type argument", str(cm.exception))

        class Subclass(WorksWithDecisions[MyDecision]):
            pass

        self.assertIs(Subclass.works_with_decision_type, MyDecision)

        class SubclassOfGenericSubclass(GenericSubclass[MyDecision]):
            pass

        self.assertIs(SubclassOfGenericSubclass.works_with_decision_type, MyDecision)

        SubclassOfGenericSubclass._check_decision_type(MyDecision)
        with self.assertRaises(TypeError) as cm:
            SubclassOfGenericSubclass._check_decision_type(int)

        self.assertIn("mismatches", str(cm.exception))


class TestAggregate(TestCase):
    def test_detects_missing_decision_type_arg_in_aggregate_subclass(self) -> None:
        class Initial(DataclassDecision):
            pass

        with self.assertRaises(TypeError) as cm:

            class BadAggregate(Aggregate):  # type: ignore[type-arg]
                @event(Initial)
                def __init__(self) -> None:
                    pass

        self.assertIn("has no decision type argument", str(cm.exception))

        # This is okay
        class GoodAggregate(Aggregate[DataclassDecision]):
            @event(Initial)
            def __init__(self) -> None:
                pass

        GoodAggregate()

    def test_detects_mismatched_decision_type(self) -> None:
        class Initial(DataclassDecision):
            pass

        with self.assertRaises(TypeError) as cm:

            class BadAggregate(Aggregate[PydanticDecision]):
                @event(Initial)
                def __init__(self) -> None:
                    pass

        self.assertIn("mismatches", str(cm.exception))

        # This is okay
        class GoodAggregate(Aggregate[DataclassDecision]):
            @event(Initial)
            def __init__(self) -> None:
                pass

        GoodAggregate()

    def test_event_sourced_property(self) -> None:
        class Initial(DataclassDecision):
            pass

        class Something(DataclassDecision):
            a: str

        class GoodAggregate(Aggregate[DataclassDecision]):
            @event(Initial)
            def __init__(self) -> None:
                self.a = ""

            @property
            def value(self) -> str:
                return self.a

            @value.setter
            @event(Something)
            def value(self, a: str) -> None:
                self.a = a

        a = GoodAggregate()

        self.assertEqual(a.a, "")
        a.value = "something"
        self.assertEqual(a.a, "something")

        new_events = a.collect_events()
        self.assertEqual(len(new_events), 2)

    def test_with_app(self) -> None:
        class Initial(DataclassDecision):
            a: int

        class Next(DataclassDecision):
            b: int

        class MyAggregate(Aggregate[DataclassDecision]):
            @event(Initial)
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event(Next)
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        app = DataclassApplication()
        app.save(a)

        copy = app.repository.get(a.id, MyAggregate)

        self.assertEqual(copy, a)

    def test_app_save_raises_type_error_for_mismatched_decision_type(self) -> None:
        class Initial(MsgspecDecision):
            a: int

        class Next(MsgspecDecision):
            b: int

        class MyAggregate(MsgspecAggregate):
            @event(Initial)
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event(Next)
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        app = PydanticApplication()
        with self.assertRaises(TypeError) as cm:
            app.save(a)  # type: ignore[arg-type]

        self.assertIn("mismatches", str(cm.exception))


class TestDataclassAggregate(TestCase):
    def test_call_aggregate_and_decorated_command_method(self) -> None:
        class Initial(DataclassDecision):
            a: int

        class Next(DataclassDecision):
            b: int

        class MyAggregate(DataclassAggregate):
            @event(Initial)
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event(Next)
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        self.assertNotEqual(a.id, NIL_UUID)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 0)
        a.do(b=2)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 2)
        collected = a.collect_events()
        self.assertEqual(len(collected), 2)
        self.assertEqual(collected[0].originator_id, a.id)
        self.assertEqual(collected[0].originator_version, 1)
        self.assertIsInstance(collected[0].decision, Initial)
        self.assertEqual(cast(Initial, collected[0].decision).a, 1)
        self.assertEqual(collected[1].originator_id, a.id)
        self.assertEqual(collected[1].originator_version, 2)
        self.assertIsInstance(collected[1].decision, Next)
        self.assertEqual(cast(Next, collected[1].decision).b, 2)

        copy: MyAggregate | None = MyAggregate.__new__(MyAggregate)
        for c in collected:
            copy = c.mutate(copy)

        self.assertEqual(copy, a)

    def test_defines_event_classes_from_given_names(self) -> None:
        class MyAggregate(DataclassAggregate):
            @event("Initial")
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event("Next")
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        self.assertNotEqual(a.id, NIL_UUID)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 0)
        a.do(b=2)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 2)
        collected = a.collect_events()
        self.assertEqual(len(collected), 2)
        self.assertEqual(collected[0].originator_id, a.id)
        self.assertEqual(collected[0].originator_version, 1)
        self.assertIsInstance(collected[0].decision, MyAggregate.Initial)  # type: ignore[attr-defined]
        self.assertEqual(collected[0].decision.a, 1)  # type: ignore[attr-defined]
        self.assertEqual(collected[1].originator_id, a.id)
        self.assertEqual(collected[1].originator_version, 2)
        self.assertIsInstance(collected[1].decision, MyAggregate.Next)  # type: ignore[attr-defined]
        self.assertEqual(collected[1].decision.b, 2)  # type: ignore[attr-defined]

        copy: MyAggregate | None = MyAggregate.__new__(MyAggregate)
        for c in collected:
            copy = c.mutate(copy)

        self.assertEqual(copy, a)


class TestPydanticAggregate(TestCase):
    def test_call_aggregate_and_decorated_command_method(self) -> None:
        class Initial(PydanticDecision):
            a: int

        class Next(PydanticDecision):
            b: int

        class MyAggregate(PydanticAggregate):
            @event(Initial)
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event(Next)
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        self.assertNotEqual(a.id, NIL_UUID)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 0)
        a.do(b=2)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 2)
        collected = a.collect_events()
        self.assertEqual(len(collected), 2)
        self.assertEqual(collected[0].originator_id, a.id)
        self.assertEqual(collected[0].originator_version, 1)
        self.assertIsInstance(collected[0].decision, Initial)
        self.assertEqual(collected[0].decision.a, 1)  # type: ignore[attr-defined]
        self.assertEqual(collected[1].originator_id, a.id)
        self.assertEqual(collected[1].originator_version, 2)
        self.assertIsInstance(collected[1].decision, Next)
        self.assertEqual(collected[1].decision.b, 2)  # type: ignore[attr-defined]

        copy: MyAggregate | None = MyAggregate.__new__(MyAggregate)
        for c in collected:
            copy = c.mutate(copy)

        self.assertEqual(copy, a)

    def test_defines_event_classes_from_given_names(self) -> None:
        class MyAggregate(PydanticAggregate):
            @event("Initial")
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event("Next")
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        self.assertNotEqual(a.id, NIL_UUID)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 0)
        a.do(b=2)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 2)
        collected = a.collect_events()
        self.assertEqual(len(collected), 2)
        self.assertEqual(collected[0].originator_id, a.id)
        self.assertEqual(collected[0].originator_version, 1)
        self.assertIsInstance(collected[0].decision, MyAggregate.Initial)  # type: ignore[attr-defined]
        self.assertEqual(collected[0].decision.a, 1)  # type: ignore[attr-defined]
        self.assertEqual(collected[1].originator_id, a.id)
        self.assertEqual(collected[1].originator_version, 2)
        self.assertIsInstance(collected[1].decision, MyAggregate.Next)  # type: ignore[attr-defined]
        self.assertEqual(collected[1].decision.b, 2)  # type: ignore[attr-defined]

        copy: MyAggregate | None = MyAggregate.__new__(MyAggregate)
        for c in collected:
            copy = c.mutate(copy)

        self.assertEqual(copy, a)


class TestMsgspecAggregate(TestCase):
    def test_call_aggregate_and_decorated_command_method(self) -> None:
        class Initial(MsgspecDecision):
            a: int

        class Next(MsgspecDecision):
            b: int

        class MyAggregate(MsgspecAggregate):
            @event(Initial)
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event(Next)
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        self.assertNotEqual(a.id, NIL_UUID)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 0)
        a.do(b=2)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 2)
        collected = a.collect_events()
        self.assertEqual(len(collected), 2)
        self.assertEqual(collected[0].originator_id, a.id)
        self.assertEqual(collected[0].originator_version, 1)
        self.assertIsInstance(collected[0].decision, Initial)
        self.assertEqual(cast(Initial, collected[0].decision).a, 1)
        self.assertEqual(collected[1].originator_id, a.id)
        self.assertEqual(collected[1].originator_version, 2)
        self.assertIsInstance(collected[1].decision, Next)
        self.assertEqual(cast(Next, collected[1].decision).b, 2)

        copy: MyAggregate | None = MyAggregate.__new__(MyAggregate)
        for c in collected:
            copy = c.mutate(copy)

        self.assertEqual(copy, a)

    def test_defines_event_classes_from_given_names(self) -> None:
        class MyAggregate(MsgspecAggregate):
            @event("Initial")
            def __init__(self, a: int):
                self.a = a
                self.b = 0

            @event("Next")
            def do(self, b: int) -> None:
                self.b = b

        a = MyAggregate(a=1)
        self.assertNotEqual(a.id, NIL_UUID)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 0)
        a.do(b=2)
        self.assertEqual(a.a, 1)
        self.assertEqual(a.b, 2)
        collected = a.collect_events()
        self.assertEqual(len(collected), 2)
        self.assertEqual(collected[0].originator_id, a.id)
        self.assertEqual(collected[0].originator_version, 1)
        self.assertIsInstance(collected[0].decision, MyAggregate.Initial)  # type: ignore[attr-defined]
        self.assertEqual(collected[0].decision.a, 1)  # type: ignore[attr-defined]
        self.assertEqual(collected[1].originator_id, a.id)
        self.assertEqual(collected[1].originator_version, 2)
        self.assertIsInstance(collected[1].decision, MyAggregate.Next)  # type: ignore[attr-defined]
        self.assertEqual(collected[1].decision.b, 2)  # type: ignore[attr-defined]

        copy: MyAggregate | None = MyAggregate.__new__(MyAggregate)
        for c in collected:
            copy = c.mutate(copy)

        self.assertEqual(copy, a)
