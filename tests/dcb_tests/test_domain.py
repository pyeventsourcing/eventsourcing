from collections.abc import Sequence
from dataclasses import dataclass
from unittest import TestCase

from eventsourcing.dcb.dataclasses import Decision
from eventsourcing.dcb.domain import (
    EnduringObject,
    Event,
    Group,
    Selector,
    Slice,
)
from eventsourcing.domain import ProgrammingError, triggers


class TestEnduringObject(TestCase):
    def test_raises_if_missing_init_method(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class Obj(EnduringObject[Decision]):
                pass

        self.assertIn("has no __init__ method", str(cm.exception))

    def test_raises_if_init_method_not_decorated(self) -> None:
        with self.assertRaises(ProgrammingError) as cm:

            class Obj(EnduringObject[Decision]):
                def __init__(self) -> None:
                    pass

        self.assertIn("is not decorated with @event decorator", str(cm.exception))

    def test_can_create_enduring_object(self) -> None:
        @dataclass
        class ObjCreated(Decision):
            obj_id: str

        class Obj(EnduringObject[Decision]):
            @triggers(ObjCreated)
            def __init__(self, obj_id: str):
                self.id = obj_id

        my_obj = Obj(obj_id="blah")
        self.assertEqual(my_obj.id, "blah")

        pending = my_obj.collect_events()
        self.assertEqual(len(pending), 1)
        event = pending[0]
        self.assertIsInstance(event, Event)
        self.assertIsInstance(event.decision, ObjCreated)
        self.assertEqual(event.decision.obj_id, "blah")

        copy = Obj.__new__(Obj)
        copy = event.decision.mutate(copy)
        self.assertEqual(copy.id, "blah")

    def test_enduring_object_with_decorated_command(self) -> None:
        @dataclass
        class ObjCreated(Decision):
            obj_id: str

        @dataclass
        class ObjUpdated(Decision):
            a: str

        class Obj(EnduringObject[Decision]):
            @triggers(ObjCreated)
            def __init__(self, obj_id: str):
                self.id = obj_id
                self.a = ""

            @triggers(ObjUpdated)
            def set_a(self, a: str) -> None:
                self.a = a

        my_obj = Obj(obj_id="blah")
        self.assertEqual(my_obj.id, "blah")
        self.assertEqual(my_obj.a, "")
        my_obj.set_a(a="a")
        self.assertEqual(my_obj.a, "a")

        pending = my_obj.collect_events()
        self.assertEqual(len(pending), 2)
        event = pending[1]
        self.assertIsInstance(event, Event)
        self.assertIsInstance(event.decision, ObjUpdated)
        self.assertEqual(event.decision.a, "a")

        copy = Obj.__new__(Obj)
        copy = pending[0].decision.mutate(copy)
        copy = pending[1].decision.mutate(copy)
        self.assertEqual(copy.id, "blah")
        self.assertEqual(my_obj.a, "a")


class TestGroup(TestCase):
    def test(self) -> None:
        @dataclass
        class Updated(Decision):
            a: str

        @dataclass
        class BothUpdated(Decision):
            a: str

        class Obj1(EnduringObject[Decision]):
            @dataclass
            class Created(Decision):
                obj1_id: str
                a: str

            @dataclass
            class Updated(Decision):
                a: str

            @triggers(Created)
            def __init__(self, obj1_id: str, a: str) -> None:
                self.id = obj1_id
                self.a = a

            @triggers(Updated)
            def set_a(self, a: str) -> None:
                self.a = a

            @triggers(BothUpdated)
            def _(self, a: str) -> None:
                self.a = a

        class Obj2(EnduringObject[Decision]):
            @dataclass
            class Created(Decision):
                obj2_id: str
                a: str

            @triggers(Created)
            def __init__(self, obj2_id: str, a: str) -> None:
                self.id = obj2_id
                self.a = a

            @triggers(Updated)
            def set_a(self, a: str) -> None:
                self.a = a

            @triggers(BothUpdated)
            def _(self, a: str) -> None:
                self.a = a

        class MyGroup(Group[Decision]):
            def __init__(self, obj1: Obj1, obj2: Obj2) -> None:
                self.obj1 = obj1
                self.obj2 = obj2

            def update_both(self, a: str) -> None:
                self.trigger_event(BothUpdated, a=a)

        obj1 = Obj1(obj1_id="obj1", a="1")
        obj2 = Obj2(obj2_id="obj1", a="2")
        group = MyGroup(obj1, obj2)
        group.update_both(a="3")
        self.assertEqual("3", group.obj1.a)
        self.assertEqual("3", group.obj2.a)

        new1 = obj1.collect_events()
        new2 = obj2.collect_events()
        new_both = group.collect_events()

        copy1 = Obj1.__new__(Obj1)
        for event in list(new1) + list(new_both):
            copy1 = event.decision.mutate(copy1)

        self.assertIsInstance(copy1, Obj1)
        assert isinstance(copy1, Obj1)  # for mypy
        self.assertEqual("3", copy1.a)

        copy2 = Obj2.__new__(Obj2)
        for event in list(new2) + list(new_both):
            copy2 = event.decision.mutate(copy2)

        self.assertIsInstance(copy2, Obj2)
        assert isinstance(copy2, Obj2)  # for mypy
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

            def consistency_boundary(
                self,
            ) -> Selector[Decision] | Sequence[Selector[Decision]]:
                return Selector(types=[Created], tags=[self.obj_id])

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

            def consistency_boundary(
                self,
            ) -> Selector[Decision] | Sequence[Selector[Decision]]:
                return Selector(types=[Created, Updated], tags=[self.obj_id])

            @triggers(Created)
            def _(self, a: str) -> None:
                self.a = a

            @triggers(Updated)
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
        for event in new:
            event.decision.mutate(update)

        self.assertEqual("1", update.a)
        self.assertEqual("2", update.new_a)

        update.execute()
        self.assertEqual("2", update.a)
        self.assertEqual("2", update.new_a)

        new = update.collect_events()

        for event in new:
            event.decision.mutate(update)

        self.assertEqual("2", update.a)
        self.assertEqual("2", update.new_a)


class TestSlideBetweenEnduringObjectsAndSlices(TestCase):
    def test(self) -> None:
        # Define an enduring object that can update "a".
        class MyObject(EnduringObject[Decision, str]):
            @dataclass
            class Created(Decision):
                myobject_id: str
                a: str

            @dataclass
            class Updated(Decision):
                a: str

            @triggers(Created)
            def __init__(self, myobject_id: str, a: str) -> None:
                self.id = myobject_id
                self.a = a

            @triggers(Updated)
            def set_a(self, a: str) -> None:
                self.a = a

        # Define a slice that will just update "a".
        class Update(Slice[Decision]):
            def __init__(self, obj_id: str, a: str):
                self.obj_id = obj_id
                self.a = ""
                self.new_a = a

            def consistency_boundary(
                self,
            ) -> Selector[Decision] | Sequence[Selector[Decision]]:
                return Selector(
                    types=[MyObject.Created, MyObject.Updated], tags=[self.obj_id]
                )

            @triggers(MyObject.Created)
            def _(self, a: str) -> None:
                self.a = a

            @triggers(MyObject.Updated)
            def _(self, a: str) -> None:
                self.a = a

            def execute(self) -> None:
                self.trigger_event(
                    MyObject.Updated,
                    tags=[self.obj_id],
                    a=self.new_a,
                )

        # Construct an enduring object and update "a".
        obj = MyObject(myobject_id="obj1", a="1")
        self.assertIsInstance(obj, MyObject)
        self.assertEqual(obj.a, "1")
        obj.set_a(a="2")
        self.assertEqual(obj.a, "2")
        new = list(obj.collect_events())

        # Construct a slice and update "a".
        update = Update(obj.id, a="3")
        for event in new:
            event.decision.mutate(update)
        update.execute()
        self.assertEqual("3", update.a)
        new.extend(update.collect_events())

        # Reconstruct enduring object from all new events.
        copy1 = MyObject.__new__(MyObject)
        for event in new:
            copy1 = event.decision.mutate(copy1)

        self.assertIsInstance(copy1, MyObject)
        assert isinstance(copy1, MyObject)  # for mypy
        self.assertEqual("3", copy1.a)

        # Define a slice that creates an enduring object.
        class Create(Slice[Decision]):
            def __init__(self, obj_id: str, a: str):
                self.obj_id = obj_id
                self.a = a

            def consistency_boundary(
                self,
            ) -> Selector[Decision] | Sequence[Selector[Decision]]:
                return Selector(types=[MyObject.Created], tags=[self.obj_id])

            def execute(self) -> None:
                self.trigger_event(
                    MyObject.Created,
                    tags=[self.obj_id],
                    myobject_id=self.obj_id,
                    a=self.a,
                )

        create = Create(obj_id="obj:123", a="1")
        create.execute()
        new = list(create.collect_events())

        copy2 = MyObject.__new__(MyObject)
        for event in new:
            copy2 = event.decision.mutate(copy2)

        self.assertIsInstance(copy2, MyObject)
        assert isinstance(copy2, MyObject)  # for mypy
        self.assertEqual("1", copy2.a)
