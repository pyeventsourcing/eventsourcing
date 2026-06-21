from collections.abc import Sequence
from dataclasses import dataclass
from unittest import TestCase, skip

from eventsourcing.dcb.dataclasses import Decision, InitialDecision
from eventsourcing.dcb.domain import (
    EnduringObject,
    Group,
    Selector,
    Slice,
    Tagged,
)
from eventsourcing.domain import ProgrammingError, event
from eventsourcing.utils import get_topic


class TestEnduringObject(TestCase):
    def test_enduring_object_with_nested_initial_decision(self) -> None:
        class MyObject(EnduringObject[Decision]):
            @dataclass
            class Created(InitialDecision):
                originator_topic: str
                myobject_id: str

        obj = MyObject()
        self.assertIsInstance(obj, MyObject)

        new = obj.collect_events()
        self.assertEqual(1, len(new))
        self.assertIsInstance(new[0], Tagged)
        self.assertIsInstance(new[0].decision, MyObject.Created)

        copy = None
        for tagged in new:
            copy = tagged.decision.mutate(copy)

        assert isinstance(copy, MyObject)
        # TODO: Maybe define __eq__
        self.assertEqual(copy.__dict__, obj.__dict__)

    def test_enduring_object_with_decorated_command_method_nested(self) -> None:
        class MyObject(EnduringObject[Decision]):
            @dataclass
            class Created(InitialDecision):
                myobject_id: str
                a: str

            @dataclass
            class Updated(Decision):
                a: str

            def __init__(self, a: str) -> None:
                self.a = a

            @event(Updated)
            def set_a(self, a: str) -> None:
                self.a = a

        obj = MyObject(a="")
        self.assertIsInstance(obj, MyObject)
        self.assertEqual(obj.a, "")

        obj.set_a(a="a")

        self.assertEqual(obj.a, "a")
        new = obj.collect_events()
        self.assertEqual(2, len(new))

        self.assertIsInstance(new[0], Tagged)
        self.assertIsInstance(new[0].decision, MyObject.Created)
        self.assertIsInstance(new[1], Tagged)
        self.assertIsInstance(new[1].decision, MyObject.Updated)

        copy = None
        for tagged in new:
            copy = tagged.decision.mutate(copy)

        assert isinstance(copy, MyObject)
        # TODO: Maybe define __eq__
        self.assertEqual(copy.__dict__, obj.__dict__)

    def test_enduring_object_with_decorated_command_method_non_nested(self) -> None:
        @dataclass
        class MyObjectUpdated(Decision):
            a: str

        class MyObject(EnduringObject[Decision]):
            @dataclass
            class Created(InitialDecision):
                originator_topic: str
                myobject_id: str
                a: str

            def __init__(self, a: str) -> None:
                self.a = a

            @event(MyObjectUpdated)
            def set_a(self, a: str) -> None:
                self.a = a

        obj = MyObject(a="")
        self.assertIsInstance(obj, MyObject)
        self.assertEqual(obj.a, "")

        obj.set_a(a="a")

        self.assertEqual(obj.a, "a")
        new = obj.collect_events()
        self.assertEqual(2, len(new))

        self.assertIsInstance(new[0], Tagged)
        self.assertIsInstance(new[0].decision, MyObject.Created)
        self.assertIsInstance(new[1], Tagged)
        self.assertIsInstance(new[1].decision, MyObjectUpdated)

        copy = None
        for tagged in new:
            copy = tagged.decision.mutate(copy)

        assert isinstance(copy, MyObject)
        # TODO: Maybe define __eq__
        self.assertEqual(copy.__dict__, obj.__dict__)

    def test_enduring_object_with_nonnested_initial_decision(self) -> None:
        @dataclass
        class Created(InitialDecision):
            originator_topic: str
            myobject_id: str
            a: str

        class MyObject(EnduringObject[Decision]):
            @event(Created)
            def __init__(self, a: str) -> None:
                self.a = a

        my_obj = MyObject(a="a")
        self.assertIsInstance(my_obj, MyObject)
        self.assertEqual(my_obj.a, "a")

    @skip("Not supported yet")
    def test_subclass_of_enduring_object_with_nested_initial_decision(self) -> None:
        class MyObject(EnduringObject[Decision]):
            @dataclass
            class Created(InitialDecision):
                originator_topic: str
                myobject_id: str

        class MySubclass(MyObject):
            pass

        my_obj = MySubclass()
        self.assertIsInstance(my_obj, MyObject)

    def test_subclass_requires_nested_initialiser(self) -> None:
        class MyObj(EnduringObject[Decision]):
            pass

        with self.assertRaisesRegex(ProgrammingError, "Please define"):
            MyObj()

    def test_subclass_initialiser_attributes_must_match(self) -> None:
        class MyObj(EnduringObject[Decision]):
            def __init__(self, a: str) -> None:
                self.a = a

            class Created(InitialDecision):
                pass

        with self.assertRaisesRegex(
            TypeError, f"Unable to construct {MyObj.Created.__qualname__}"
        ):
            MyObj(a="a")

    def test_nice_error_when_initialiser_cannot_construct_enduring_object(self) -> None:
        class MyObj(EnduringObject[Decision]):
            def __init__(self) -> None:
                pass

            class Created(InitialDecision):
                def __init__(
                    self, myobj_id: str, originator_topic: str, tags: list[str], a: str
                ) -> None:
                    self.myobj_id = myobj_id
                    self.originator_topic = originator_topic
                    self.a = a

        with self.assertRaisesRegex(TypeError, "Unable to construct"):
            MyObj(a="a")  # type: ignore[call-arg]

    def test_initial_decision_mutate_raises_type_error(self) -> None:

        @dataclass
        class MyInitialDecision(InitialDecision):
            originator_topic: str

        decision = MyInitialDecision(originator_topic=get_topic(type(self)))
        with self.assertRaises(TypeError) as cm:
            decision.mutate(None)

        self.assertTrue(
            "Originator type not subclass of EnduringObject" in str(cm.exception)
        )


class TestGroup(TestCase):
    def test(self) -> None:
        @dataclass
        class Updated(Decision):
            a: str

        @dataclass
        class BothUpdated(Decision):
            a: str

        class MyObject1(EnduringObject[Decision]):
            @dataclass
            class Created(InitialDecision):
                originator_topic: str
                myobject1_id: str
                a: str

            @dataclass
            class Updated(Decision):
                a: str

            def __init__(self, a: str) -> None:
                self.a = a

            @event(Updated)
            def set_a(self, a: str) -> None:
                self.a = a

            @event(BothUpdated)
            def _(self, a: str) -> None:
                self.a = a

        class MyObject2(EnduringObject[Decision]):
            @dataclass
            class Created(InitialDecision):
                originator_topic: str
                myobject2_id: str
                a: str

            def __init__(self, a: str) -> None:
                self.a = a

            @event(Updated)
            def set_a(self, a: str) -> None:
                self.a = a

            @event(BothUpdated)
            def _(self, a: str) -> None:
                self.a = a

        class MyGroup(Group[Decision]):
            def __init__(self, obj1: MyObject1, obj2: MyObject2) -> None:
                self.obj1 = obj1
                self.obj2 = obj2

            def update_both(self, a: str) -> None:
                self.trigger_event(BothUpdated, a=a)

        obj1 = MyObject1(a="1")
        obj2 = MyObject2(a="2")
        group = MyGroup(obj1, obj2)
        group.update_both(a="3")
        self.assertEqual("3", group.obj1.a)
        self.assertEqual("3", group.obj2.a)

        new1 = obj1.collect_events()
        new2 = obj2.collect_events()
        new_both = group.collect_events()

        copy1 = None
        for tagged in list(new1) + list(new_both):
            copy1 = tagged.decision.mutate(copy1)

        self.assertIsInstance(copy1, MyObject1)
        assert isinstance(copy1, MyObject1)  # for mypy
        self.assertEqual("3", copy1.a)

        copy2 = None
        for tagged in list(new2) + list(new_both):
            copy2 = tagged.decision.mutate(copy2)

        self.assertIsInstance(copy2, MyObject2)
        assert isinstance(copy2, MyObject2)  # for mypy
        self.assertEqual("3", copy2.a)


class TestSlice(TestCase):
    def test_slice(self) -> None:
        @dataclass
        class Created(Decision):
            a: str

        @dataclass
        class Updated(Decision):
            a: str

        class Create(Slice[Decision]):
            def __init__(self, obj_id: str, a: str) -> None:
                self.obj_id = obj_id
                self.a = a

            def consistency_boundary(self) -> Selector | Sequence[Selector]:
                return Selector(types=type(self).projected_types, tags=[self.obj_id])

            def execute(self) -> None:
                self.trigger_event(
                    Created,
                    tags=[self.obj_id],
                    a=self.a,
                )

        class Update(Slice[Decision]):
            def __init__(self, obj_id: str, a: str):
                self.obj_id = obj_id
                self.a = ""
                self.new_a = a

            def consistency_boundary(self) -> Selector | Sequence[Selector]:
                return Selector(types=type(self).projected_types, tags=[self.obj_id])

            @event(Created)
            def _(self, a: str) -> None:
                self.a = a

            @event(Updated)
            def _(self, a: str) -> None:
                self.a = a

            def execute(self) -> None:
                self.trigger_event(
                    Updated,
                    tags=[self.obj_id],
                    a=self.new_a,
                )

        obj_id = "obj1"
        create = Create(obj_id=obj_id, a="1")
        create.execute()
        new = create.collect_events()

        update = Update(obj_id=obj_id, a="2")
        for tagged in new:
            tagged.decision.mutate(update)

        self.assertEqual("1", update.a)
        self.assertEqual("2", update.new_a)

        update.execute()
        self.assertEqual("2", update.a)
        self.assertEqual("2", update.new_a)

        new = update.collect_events()

        for tagged in new:
            tagged.decision.mutate(update)

        self.assertEqual("2", update.a)
        self.assertEqual("2", update.new_a)


class TestSlideBetweenEnduringObjectsAndSlices(TestCase):
    def test(self) -> None:
        # Define an enduring object that can update "a".
        class MyObject(EnduringObject[Decision, str]):
            @dataclass
            class Created(InitialDecision):
                originator_topic: str
                myobject_id: str
                a: str

            @dataclass
            class Updated(Decision):
                a: str

            def __init__(self, a: str) -> None:
                self.a = a

            @event(Updated)
            def set_a(self, a: str) -> None:
                self.a = a

        # Define a slice that will just update "a".
        class Update(Slice[Decision]):
            def __init__(self, obj_id: str, a: str):
                self.obj_id = obj_id
                self.a = ""
                self.new_a = a

            def consistency_boundary(self) -> Selector | Sequence[Selector]:
                return Selector(types=type(self).projected_types, tags=[self.obj_id])

            @event(MyObject.Created)
            def _(self, a: str) -> None:
                self.a = a

            @event(MyObject.Updated)
            def _(self, a: str) -> None:
                self.a = a

            def execute(self) -> None:
                self.trigger_event(
                    MyObject.Updated,
                    tags=[self.obj_id],
                    a=self.new_a,
                )

        # Construct an enduring object and update "a".
        obj = MyObject(a="1")
        self.assertIsInstance(obj, MyObject)
        self.assertEqual(obj.a, "1")
        obj.set_a(a="2")
        self.assertEqual(obj.a, "2")
        new = list(obj.collect_events())

        # Construct a slice and update "a".
        update = Update(obj.id, a="3")
        for tagged in new:
            tagged.decision.mutate(update)
        update.execute()
        self.assertEqual("3", update.a)
        new.extend(update.collect_events())

        # Reconstruct enduring object from all new events.
        copy1 = None
        for tagged in new:
            copy1 = tagged.decision.mutate(copy1)

        self.assertIsInstance(copy1, MyObject)
        assert isinstance(copy1, MyObject)  # for mypy
        self.assertEqual("3", copy1.a)

        # Define a slice that creates an enduring object.
        class Create(Slice[Decision]):
            def __init__(self, obj_id: str, a: str):
                self.obj_id = obj_id
                self.a = a

            def consistency_boundary(self) -> Selector | Sequence[Selector]:
                return Selector(types=[MyObject.Created], tags=[self.obj_id])

            def execute(self) -> None:
                self.trigger_event(
                    MyObject.Created,
                    tags=[self.obj_id],
                    originator_topic=get_topic(MyObject),
                    myobject_id=self.obj_id,
                    a=self.a,
                )

        create = Create(obj_id="obj:123", a="1")
        create.execute()
        new = list(create.collect_events())

        copy2 = None
        for tagged in new:
            copy2 = tagged.decision.mutate(copy2)

        self.assertIsInstance(copy2, MyObject)
        assert isinstance(copy2, MyObject)  # for mypy
        self.assertEqual("1", copy2.a)
