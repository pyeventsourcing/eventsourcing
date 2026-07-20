# from __future__ import annotations
#
# import contextlib
# from dataclasses import dataclass
# from datetime import UTC, datetime
# from typing import Any
# from unittest import TestCase
# from uuid import NAMESPACE_URL, UUID, uuid5
#
# from eventsourcing.application import Application
# from eventsourcing.domain_old import (
#     Aggregate,
#     AggregateCreated,
#     AggregateEvent,
#     aggregate,
# )
# from eventsourcing.domain_new import datetime_now_with_tzinfo, event, triggers
# from eventsourcing.utils import get_method_name
#
#
# class TestAggregateDecorator(TestCase):
#     def test_decorate_class_with_no_bases(self) -> None:
#         @aggregate
#         class MyAgg:
#             """My doc"""
#
#             a: int
#
#         self.assertTrue(issubclass(MyAgg, Aggregate))
#         self.assertTrue(issubclass(MyAgg, MyAgg))
#         self.assertTrue(MyAgg.__name__, "MyAgg")
#         self.assertTrue(MyAgg.__doc__, "My doc")
#         self.assertEqual(MyAgg.__bases__, (Aggregate,))
#         self.assertEqual(MyAgg.__annotations__, {"a": "int"})
#
#         agg = MyAgg(a=1)  # type: ignore[call-arg]
#         self.assertEqual(agg.a, 1)  # pyright: ignore [reportAttributeAccessIssue]
#         self.assertEqual(len(agg.pending_events), 1)  # type: ignore[attr-defined]
#         self.assertIsInstance(agg, Aggregate)
#         self.assertIsInstance(agg, MyAgg)
#
#     def test_decorate_class_with_one_base(self) -> None:
#         class MyBase:
#             """My base doc"""
#
#         @aggregate
#         class MyAgg(MyBase):
#             """My doc"""
#
#             a: int
#
#         self.assertTrue(issubclass(MyAgg, Aggregate))
#         self.assertTrue(issubclass(MyAgg, MyAgg))
#         self.assertTrue(issubclass(MyAgg, MyBase))
#         self.assertTrue(MyAgg.__name__, "MyAgg")
#         self.assertTrue(MyAgg.__doc__, "My doc")
#         self.assertEqual(MyAgg.__bases__, (MyBase, Aggregate))
#         self.assertEqual(MyAgg.__annotations__, {"a": "int"})
#
#         agg = MyAgg(a=1)  # type: ignore[call-arg]
#         self.assertEqual(agg.a, 1)  # pyright: ignore [reportAttributeAccessIssue]
#         self.assertEqual(len(agg.pending_events), 1)  # type: ignore[attr-defined]
#         self.assertIsInstance(agg, Aggregate)
#         self.assertIsInstance(agg, MyAgg)
#         self.assertIsInstance(agg, MyBase)
#
#     def test_decorate_class_with_two_bases(self) -> None:
#         class MyAbstract:
#             """My base doc"""
#
#         class MyBase(MyAbstract):
#             """My base doc"""
#
#         @aggregate
#         class MyAgg(MyBase):
#             """My doc"""
#
#             a: int
#
#         self.assertTrue(issubclass(MyAgg, Aggregate))
#         self.assertTrue(issubclass(MyAgg, MyAgg))
#         self.assertTrue(issubclass(MyAgg, MyBase))
#         self.assertTrue(issubclass(MyAgg, MyAbstract))
#         self.assertTrue(MyAgg.__name__, "MyAgg")
#         self.assertTrue(MyAgg.__doc__, "My doc")
#         self.assertEqual(MyAgg.__bases__, (MyBase, Aggregate))
#         self.assertEqual(MyAgg.__annotations__, {"a": "int"})
#
#         agg = MyAgg(a=1)  # type: ignore[call-arg]
#         self.assertEqual(agg.a, 1)  # pyright: ignore [reportAttributeAccessIssue]
#         self.assertEqual(len(agg.pending_events), 1)  # type: ignore[attr-defined]
#         self.assertIsInstance(agg, Aggregate)
#         self.assertIsInstance(agg, MyAgg)
#         self.assertIsInstance(agg, MyBase)
#         self.assertIsInstance(agg, MyAbstract)
#
#     def test_raises_when_decorating_aggregate_subclass(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             @aggregate
#             class MyAgg(Aggregate):
#                 pass
#
#         self.assertIn("MyAgg is already an Aggregate", cm.exception.args[0])
#
#     def test_aggregate_on_dataclass(self) -> None:
#         @aggregate
#         @dataclass
#         class MyAgg:
#             value: int
#
#         a = MyAgg(1)  # pyright: ignore [reportCallIssue]
#         self.assertIsInstance(a, MyAgg)
#         self.assertEqual(a.value, 1)  # pyright: ignore [reportAttributeAccessIssue]
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 1)  # type: ignore[attr-defined]
#
#     def test_dataclass_on_aggregate(self) -> None:
#         @dataclass
#         @aggregate
#         class MyAgg:
#             value: int
#
#         a = MyAgg(1)  # pyright: ignore [reportCallIssue]
#         self.assertIsInstance(a, MyAgg)
#         self.assertEqual(a.value, 1)  # pyright: ignore [reportAttributeAccessIssue]
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 1)  # type: ignore[attr-defined]
#
#     def test_aggregate_decorator_called_with_create_event_name(self) -> None:
#         @aggregate(created_event_name="Started")
#         class MyAgg:
#             value: int
#
#         a = MyAgg(1)  # type: ignore[call-arg]
#         self.assertIsInstance(a, MyAgg)
#         self.assertEqual(a.value, 1)  # pyright: ignore [reportAttributeAccessIssue]
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 1)  # type: ignore[attr-defined]
#         self.assertEqual(type(a.pending_events[0]).__name__, "Started")  # type: ignor
#         e[attr-defined]
#
#
# class TestEventDecorator(TestCase):
#     def test_event_name_inferred_from_method_no_args(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def heartbeat(self) -> None:
#                 pass
#
#         a = MyAgg()
#         self.assertIsInstance(a, MyAgg)
#         a.heartbeat()
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(a.version, 2)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.Heartbeat)  # type: ignore[at
#         tr-defined]
#
#     def test_event_decorator_called_without_args(self) -> None:
#         class MyAgg(Aggregate):
#             @event()
#             def heartbeat(self) -> None:
#                 pass
#
#         a = MyAgg()
#         self.assertIsInstance(a, MyAgg)
#         a.heartbeat()
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(a.version, 2)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.Heartbeat)  # type: ignore[at
#         tr-defined]
#
#     def test_event_name_inferred_from_method_with_arg(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, value: int) -> None:
#                 self.value = value
#
#         a = MyAgg()
#         self.assertIsInstance(a, MyAgg)
#         a.value_changed(1)
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(a.version, 2)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_event_name_inferred_from_method_with_kwarg(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, value: int) -> None:
#                 self.value = value
#
#         a = MyAgg()
#         self.assertIsInstance(a, MyAgg)
#         a.value_changed(value=1)
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_event_name_inferred_from_method_with_default_kwarg(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, value: int = 3) -> None:
#                 self.value = value
#
#         a = MyAgg()
#         self.assertIsInstance(a, MyAgg)
#         self.assertIsInstance(a, Aggregate)
#
#         # Call the method.
#         a.value_changed()
#
#         # Check default value is assigned.
#         self.assertEqual(a.value, 3)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#         self.assertEqual(a.pending_events[1].value, 3)  # type: ignore[attr-defined]
#
#         # Check the default doesn't take precedence over given value.
#         a.value_changed(4)
#         self.assertEqual(a.value, 4)
#         self.assertEqual(len(a.pending_events), 3)
#         self.assertIsInstance(a.pending_events[2], MyAgg.ValueChanged)
#         [attr-defined]
#         self.assertEqual(a.pending_events[2].value, 4)  # type: ignore[attr-defined]
#
#     def test_method_name_same_on_class_and_instance(self) -> None:
#         # Check this works with Python object class.
#         class MyClass:
#             def value_changed(self) -> None:
#                 pass
#
#         a = MyClass()
#
#         self.assertEqual(
#             get_method_name(a.value_changed), get_method_name(MyClass.value_changed)
#         )
#
#         # Check this works with Aggregate class and @event decorator.
#         class MyAggregate(Aggregate):
#             @event
#             def value_changed(self) -> None:
#                 pass
#
#         a1 = MyAggregate()
#
#         self.assertEqual(
#             get_method_name(a1.value_changed),
#             get_method_name(MyAggregate.value_changed),
#         )
#
#         self.assertTrue(
#             get_method_name(a1.value_changed).endswith("value_changed"),
#         )
#
#         self.assertTrue(
#             get_method_name(MyAggregate.value_changed).endswith("value_changed"),
#         )
#
#         # Check this works with Aggregate class and @event decorator.
#         class MyAggregate2(Aggregate):
#             @event()
#             def value_changed(self) -> None:
#                 pass
#
#         a2 = MyAggregate2()
#
#         self.assertEqual(
#             get_method_name(a2.value_changed),
#             get_method_name(MyAggregate2.value_changed),
#         )
#
#         self.assertTrue(
#             get_method_name(a2.value_changed).endswith("value_changed"),
#         )
#
#         self.assertTrue(
#             get_method_name(MyAggregate2.value_changed).endswith("value_changed"),
#         )
#
#     def test_raises_when_method_takes_1_positional_argument_but_2_were_given(
#         self,
#     ) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed(1)  # type: ignore[call-arg]
#
#             name = get_method_name(cls.value_changed)
#
#             self.assertEqual(
#                 f"{name}() takes 1 positional argument but 2 were given",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_takes_2_positional_argument_but_3_were_given(
#         self,
#     ) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, value: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, value: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed(1, 2)  # type: ignore[call-arg]
#             name = get_method_name(cls.value_changed)
#             self.assertEqual(
#                 f"{name}() takes 2 positional arguments but 3 were given",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_missing_1_required_positional_argument(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, a: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed()  # type: ignore[call-arg]
#             name = get_method_name(cls.value_changed)
#             self.assertEqual(
#                 f"{name}() missing 1 required positional argument: 'a'",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_missing_2_required_positional_arguments(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int, b: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, a: int, b: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed()  # type: ignore[call-arg]
#             name = get_method_name(obj.value_changed)
#             self.assertEqual(
#                 f"{name}() missing 2 required positional arguments: 'a' and 'b'",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_missing_3_required_positional_arguments(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int, b: int, c: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, a: int, b: int, c: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed()  # type: ignore[call-arg]
#
#             name = get_method_name(cls.value_changed)
#
#             self.assertEqual(
#                 f"{name}() missing 3 required positional arguments: 'a', 'b', and 'c'"
#                 ,
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_missing_1_required_keyword_only_argument(self) -> None
#     :
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int, *, b: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, a: int, *, b: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed(1)  # type: ignore[call-arg]
#
#             name = get_method_name(cls.value_changed)
#             self.assertEqual(
#                 f"{name}() missing 1 required keyword-only argument: 'b'",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_missing_2_required_keyword_only_arguments(self) -> Non
#     e:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int, *, b: int, c: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, a: int, *, b: int, c: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed(1)  # type: ignore[call-arg]
#
#             name = get_method_name(cls.value_changed)
#             self.assertEqual(
#                 f"{name}() missing 2 required keyword-only arguments: 'b' and 'c'",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_missing_3_required_keyword_only_arguments(self) -> Non
#     e:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int, *, b: int, c: int, d: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, a: int, *, b: int, c: int, d: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed(1)  # type: ignore[call-arg]
#
#             name = get_method_name(cls.value_changed)
#             self.assertEqual(
#                 f"{name}() missing 3 required keyword-only arguments: "
#                 "'b', 'c', and 'd'",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_missing_positional_and_required_keyword_only_arguments(
#         self,
#     ) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int, *, b: int, c: int, d: int) -> None:
#                 pass
#
#         class Data:
#             def value_changed(self, a: int, *, b: int, c: int, d: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[MyAgg | Data]) -> None:
#             obj = cls()
#
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed()  # type: ignore[call-arg]
#
#             name = get_method_name(cls.value_changed)
#             self.assertEqual(
#                 f"{name}() missing 1 required positional argument: 'a'",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_gets_unexpected_keyword_argument(self) -> None:
#         class Data:
#             def value_changed(self, a: int) -> None:
#                 pass
#
#         class MyAgg(Aggregate):
#             @event
#             def value_changed(self, a: int) -> None:
#                 pass
#
#         def assert_raises(cls: type[Data | MyAgg]) -> None:
#             obj = cls()
#
#             with self.assertRaises(TypeError) as cm:
#                 obj.value_changed(b=1)  # type: ignore[call-arg]
#
#             name = get_method_name(cls.value_changed)
#             self.assertEqual(
#                 f"{name}() got an unexpected keyword argument 'b'",
#                 cm.exception.args[0],
#             )
#
#         assert_raises(MyAgg)
#         assert_raises(Data)
#
#     def test_raises_when_method_is_staticmethod(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class _(Aggregate):
#                 @event
#                 @staticmethod
#                 def value_changed() -> None:
#                     pass
#
#         self.assertIn(
#             "is not a str, function, property, or subclass of CanMutateAggregate",
#             cm.exception.args[0],
#         )
#
#         with self.assertRaises(TypeError) as cm:
#
#             class MyAgg(Aggregate):
#                 @event("ValueChanged")
#                 @staticmethod
#                 def value_changed() -> None:
#                     pass
#
#         self.assertTrue(
#             cm.exception.args[0].endswith(
#                 " is not a function or property",
#             ),
#             cm.exception.args[0],
#         )
#
#     def test_raises_when_method_is_classmethod(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class _(Aggregate):
#                 @event
#                 @classmethod
#                 def value_changed(cls) -> None:
#                     pass
#
#         self.assertIn(
#             "is not a str, function, property, or subclass of CanMutateAggregate",
#             cm.exception.args[0],
#         )
#
#         with self.assertRaises(TypeError) as cm:
#
#             class MyAgg(Aggregate):
#                 @event("ValueChanged")
#                 @classmethod
#                 def value_changed(cls) -> None:
#                     pass
#
#         self.assertTrue(
#             cm.exception.args[0].endswith(
#                 " is not a function or property",
#             ),
#             cm.exception.args[0],
#         )
#
#     def test_method_called_with_positional_defined_with_keyword_params(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def values_changed(
#                 self, a: int | None = None, b: int | None = None
#             ) -> None:
#                 self.a = a
#                 self.b = b
#
#         a = MyAgg()
#         a.values_changed()
#
#         self.assertEqual(a.a, None)
#         self.assertEqual(a.b, None)
#
#         a.values_changed(1, 2)
#
#         self.assertEqual(a.a, 1)
#         self.assertEqual(a.b, 2)
#
#     def test_method_called_with_keyword_defined_with_positional_params(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def values_changed(self, a: int, b: int) -> None:
#                 self.a = a
#                 self.b = b
#
#         a = MyAgg()
#         a.values_changed(a=1, b=2)
#
#         self.assertEqual(a.a, 1)
#         self.assertEqual(a.b, 2)
#
#     # @skipIf(sys.version_info[0:2] < (3, 8), "Positional only params not supported")
#     # def test_method_called_with_keyword_defined_with_positional_only(self) -> None:
#     #     @aggregate
#     #     class MyAgg:
#     #         @event
#     #         def values_changed(self, a, b, /):
#     #             self.a = a
#     #             self.b = b
#     #
#     #     a = MyAgg()
#     #     a.values_changed(1, 2)
#
#     # def test_raises_when_method_has_positional_only_params(self) -> None:
#     #     @aggregate
#     #     class MyAgg:
#     #         @event
#     #         def values_changed(self, a, b, /):
#     #             self.a = a
#     #             self.b = b
#     #
#     #     with self.assertRaises(TypeError) as cm:
#     #
#     #         a = MyAgg()
#     #         a.values_changed(1, 2)
#     #
#     #     self.assertTrue(
#     #         cm.exception.args[0].startswith(
#     #             # "values_changed() got some positional-only arguments"
#     #             "Can't construct event"
#     #         ),
#     #         cm.exception.args[0],
#     #     )
#
#     def test_raises_when_decorated_method_called_directly_without_instance_arg(
#         self,
#     ) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def method(self) -> None:
#                 pass
#
#         with self.assertRaises(TypeError) as cm:
#             MyAgg.method()  # type: ignore[call-arg]
#         self.assertEqual(
#             cm.exception.args[0],
#             "Expected aggregate as first argument",
#         )
#
#     def test_decorated_method_called_directly_on_class(self) -> None:
#         class MyAgg(Aggregate):
#             @event
#             def method(self) -> None:
#                 pass
#
#         a = MyAgg()
#         self.assertEqual(a.version, 1)
#         MyAgg.method(a)
#         self.assertEqual(a.version, 2)
#
#     def test_event_name_set_in_decorator(self) -> None:
#         class MyAgg(Aggregate):
#             @event("ValueChanged")
#             def set_value(self, value: int) -> None:
#                 self.value = value
#
#         a = MyAgg()
#         a.set_value(value=1)
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_event_called_to_redefine_method_with_explicit_name(self) -> None:
#         class MyAgg(Aggregate):
#             def set_value(self, value: int) -> None:
#                 self.value = value
#
#             set_value = event("ValueChanged")(set_value)
#
#         a = MyAgg()
#         a.set_value(value=1)
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_event_called_to_redefine_method_with_implied_name(self) -> None:
#         class MyAgg(Aggregate):
#             def value_changed(self, value: int) -> None:
#                 self.value = value
#
#             set_value = event(value_changed)
#
#         a = MyAgg()
#         a.set_value(value=1)
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_event_name_set_in_decorator_cannot_be_empty_string(self) -> None:
#         with self.assertRaises(ValueError) as cm:
#
#             class MyAgg(Aggregate):
#                 @event("")
#                 def set_value(self, value: int) -> None:
#                     self.value = value
#
#         self.assertEqual(
#             cm.exception.args[0], "Can't use empty string as name of event class"
#         )
#
#     def test_event_with_name_decorates_property(self) -> None:
#         class MyAgg(Aggregate):
#             def __init__(self, value: int) -> None:
#                 self._value = value
#
#             @property
#             def value(self) -> int:
#                 return self._value
#
#             @event("ValueChanged")  # type: ignore[misc]
#             @value.setter
#             def value(self, x: int) -> None:
#                 self._value = x
#
#         a = MyAgg(0)
#         self.assertEqual(a.value, 0)
#         a.value = 1  # type: ignore[misc]
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_property_decorates_event_with_name(self) -> None:
#         class MyAgg(Aggregate):
#             @property
#             def value(self) -> int:
#                 return self._value
#
#             @value.setter
#             @event("ValueChanged")
#             def value(self, x: int) -> None:
#                 self._value = x
#
#         a = MyAgg()
#         a.value = 1
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_property_called_with_decorated_set_method_with_name_given(self) -> None:
#         class MyAgg(Aggregate):
#             def get_value(self) -> int:
#                 return self._value
#
#             @event("ValueChanged")
#             def set_value(self, x: int) -> None:
#                 self._value = x
#
#             value = property(get_value, set_value)
#
#         a = MyAgg()
#         a.value = 1
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_property_called_with_decorated_set_method_with_name_inferred(self) -> Non
#     e:
#         class MyAgg(Aggregate):
#             def get_value(self) -> int:
#                 return self._value
#
#             @event
#             def value_changed(self, x: int) -> None:
#                 self._value = x
#
#             value = property(get_value, value_changed)
#
#         a = MyAgg()
#         a.value = 1
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_property_called_with_wrapped_set_method_with_name_given(self) -> None:
#         class MyAgg(Aggregate):
#             def get_value(self) -> int:
#                 return self._value
#
#             def set_value(self, x: int) -> None:
#                 self._value = x
#
#             value = property(get_value, event("ValueChanged")(set_value))
#
#         a = MyAgg()
#         a.value = 1
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_property_called_with_wrapped_set_method_with_name_inferred(self) -> None:
#         class MyAgg(Aggregate):
#             def get_value(self) -> int:
#                 return self._value
#
#             def value_changed(self, x: int) -> None:
#                 self._value = x
#
#             value = property(get_value, event(value_changed))
#
#         a = MyAgg()
#         a.value = 1
#         self.assertEqual(a.value, 1)
#         self.assertIsInstance(a, Aggregate)
#         self.assertEqual(len(a.pending_events), 2)
#         self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)
#         [attr-defined]
#
#     def test_raises_when_event_decorates_property_getter(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class MyAgg(Aggregate):
#                 @event("ValueChanged")  # type: ignore[prop-decorator]
#                 @property
#                 def value(self) -> None:
#                     return None
#
#         self.assertEqual(
#             cm.exception.args[0], "@event can't decorate value() property getter"
#         )
#
#         with self.assertRaises(TypeError) as cm:
#
#             @aggregate
#             class _:
#                 @event("ValueChanged")  # type: ignore[prop-decorator]
#                 @property
#                 def value(self) -> None:
#                     return None
#
#         self.assertEqual(
#             cm.exception.args[0], "@event can't decorate value() property getter"
#         )
#
#     def test_raises_when_event_without_name_decorates_property(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class MyAgg(Aggregate):
#                 def __init__(self, _: Any) -> None:
#                     pass
#
#                 @property
#                 def value(self) -> None:
#                     return None
#
#                 @event  # type: ignore[misc]
#                 @value.setter
#                 def value(self, x: int) -> None:
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0],
#             "@event decorator on @value.setter requires event name or class",
#         )
#
#     def test_raises_when_property_decorates_event_without_name(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class MyAgg(Aggregate):
#                 def __init__(self, _: Any) -> None:
#                     pass
#
#                 @property
#                 def value(self) -> None:
#                     return None
#
#                 @value.setter
#                 @event
#                 def value(self, _: Any) -> None:
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0],
#             "@event decorator under @value.setter requires event name or class",
#         )
#
#     def test_raises_when_event_decorator_used_with_wrong_args(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#             event(1)  # type: ignore[call-overload]
#         self.assertEqual(
#             "1 is not a str, function, property, or subclass of CanMutateAggregate",
#             cm.exception.args[0],
#         )
#
#         with self.assertRaises(TypeError) as cm:
#             event("EventName")(1)  # type: ignore[type-var]
#         self.assertEqual(
#             "1 is not a function or property",
#             cm.exception.args[0],
#         )
#
#     def test_raises_when_decorated_method_has_variable_args(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class _1(Aggregate):
#                 @event  # no event name
#                 def method(self, *args: Any) -> None:
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0], "*args not supported by decorator on method()"
#         )
#
#         with self.assertRaises(TypeError) as cm:
#
#             class _2(Aggregate):
#                 @event("EventName")  # has event name
#                 def method(self, *args: Any) -> None:
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0], "*args not supported by decorator on method()"
#         )
#
#     def test_raises_when_decorated_method_has_variable_kwargs(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class _1(Aggregate):
#                 @event  # no event name
#                 def method(self, **kwargs: Any) -> None:
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0], "**kwargs not supported by decorator on method()"
#         )
#
#         with self.assertRaises(TypeError) as cm:
#
#             class _2(Aggregate):
#                 @event("EventName")  # has event name
#                 def method(self, **kwargs: Any) -> None:
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0], "**kwargs not supported by decorator on method()"
#         )
#
#         # With property.
#         with self.assertRaises(TypeError) as cm:
#
#             class _3(Aggregate):
#                 @property
#                 def name(self) -> None:
#                     return None
#
#                 # before setter
#                 @event("EventName")  # type: ignore[misc]
#                 @name.setter
#                 def name(self, **kwargs: Any) -> None:
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0], "**kwargs not supported by decorator on name()"
#         )
#
#         with self.assertRaises(TypeError) as cm:
#
#             class _4(Aggregate):
#                 @property
#                 def name(self) -> None:
#                     return None
#
#                 @name.setter
#                 @event("EventName")  # after setter (same as without property)
#                 def name(self, **kwargs: Any) -> None:  # type: ignore[misc]
#                     pass
#
#         self.assertEqual(
#             cm.exception.args[0], "**kwargs not supported by decorator on name()"
#         )
#
#     # TODO: Somehow deal with custom decorators?
#     # def test_custom_decorators(self) -> None:
#     #
#     #     def mydecorator(f):
#     #         def g(*args, **kwargs):
#     #             f(*args, **kwargs)
#     #         return g
#     #
#     #     @aggregate
#     #     class MyAgg:
#     #         @event
#     #         @mydecorator
#     #         def method(self) -> None:
#     #             raise Exception("Shou")
#     #
#     #     a = MyAgg()
#     #     a.method()
#     #
#
#     def test_event_decorator_uses_explicit_event_classes(self) -> None:
#         # Here we just use the @event decorator to trigger events
#         # that are applied using the decorated method.
#         @aggregate
#         class Order:
#             class Confirmed(AggregateEvent):
#                 at: datetime
#
#             @triggers(Confirmed)
#             def confirm(self, at: datetime) -> None:
#                 self.confirmed_at = at
#
#         order = Order()
#
#         order.confirm(  # pyright: ignore [reportAttributeAccessIssue]
#             datetime_now_with_tzinfo()
#         )
#         self.assertIsInstance(
#             order.confirmed_at,  # pyright: ignore [reportAttributeAccessIssue]
#             datetime,
#         )
#
#         app = Application()
#         app.save(order)  # type: ignore[arg-type]
#
#         copy = app.repository.get(order.id, Order)
#
#         self.assertEqual(
#             copy.confirmed_at,  # pyright: ignore [reportAttributeAccessIssue]
#             order.confirmed_at,  # pyright: ignore [reportAttributeAccessIssue]
#         )
#
#         self.assertIsInstance(order, Aggregate)
#         self.assertIsInstance(order, Order)
#         self.assertIsInstance(copy, Aggregate)
#         self.assertIsInstance(copy, Order)
#
#     def test_apply_method_is_called_when_event_used_in_decorator(self) -> None:
#         class CanConfirm(Aggregate):
#             def __init__(self) -> None:
#                 self.is_confirmed1 = False
#                 self.is_confirmed2 = False
#
#             class Confirmed(AggregateEvent):
#                 def apply(self, aggregate: CanConfirm) -> None:
#                     aggregate.is_confirmed2 = True
#
#             @triggers(Confirmed)
#             def confirm(self) -> None:
#                 if self.is_confirmed1:
#                     msg = "Confirmed already confirmed"
#                     raise AssertionError(msg)
#                 self.is_confirmed1 = True
#
#         a = CanConfirm()
#         self.assertFalse(a.is_confirmed1)
#         self.assertFalse(a.is_confirmed2)
#         self.assertEqual(a.version, 1)
#
#         a.confirm()
#         self.assertTrue(a.is_confirmed1)
#         self.assertTrue(a.is_confirmed2)
#         self.assertEqual(a.version, 2)
#
#         a.is_confirmed2 = False
#         with self.assertRaises(AssertionError):
#             a.confirm()
#
#         # Check Confirmed.apply() method isn't called.
#         self.assertFalse(a.is_confirmed2)
#         self.assertEqual(a.version, 2)
#
#     def test_raises_when_event_class_already_defined(self) -> None:
#         # Here we just use the @event decorator to trigger events
#         # that are applied using the decorated method.
#         with self.assertRaises(TypeError) as cm:
#
#             class Order(Aggregate):
#                 class Confirmed(AggregateEvent):
#                     at: datetime
#
#                 @triggers("Confirmed")
#                 def confirm(self, at: datetime) -> None:
#                     self.confirmed_at = at
#
#         self.assertEqual(
#             cm.exception.args[0], "Confirmed event already defined on Order"
#         )
#
#     def test_raises_when_event_class_name_used_twice(self) -> None:
#         # Here we make sure the same event class name can't be
#         # declared on two decorators.
#         with self.assertRaises(TypeError) as cm:
#
#             # @aggregate
#             class Order(Aggregate):
#                 @triggers("Confirmed")
#                 def confirm1(self, at: datetime) -> None:
#                     self.confirmed_at = at
#
#                 @triggers("Confirmed")
#                 def confirm2(self, at: datetime) -> None:
#                     self.confirmed_at = at
#
#         self.assertEqual(
#             cm.exception.args[0], "Confirmed event already defined on Order"
#         )
#
#     def test_raises_when_event_class_used_twice(self) -> None:
#         # Here we make sure the same event class can't be
#         # mentioned on two decorators.
#         with self.assertRaises(TypeError) as cm:
#
#             @aggregate
#             class Order(Aggregate):
#                 class Confirmed(AggregateEvent):
#                     at: datetime
#
#                 @triggers(Confirmed)
#                 def confirm1(self, at: datetime) -> None:
#                     self.confirmed_at = at
#
#                 @triggers(Confirmed)
#                 def confirm2(self, at: datetime) -> None:
#                     self.confirmed_at = at
#
#         self.assertEqual(
#             cm.exception.args[0],
#             "Confirmed event class used in more than one decorator",
#         )
#
#     def test_dirty_style_isnt_so_dirty_after_all(self) -> None:
#         class Order(Aggregate):
#             def __init__(self, name: str) -> None:
#                 self.name = name
#                 self.confirmed_at: datetime | None = None
#                 self.pickedup_at: datetime | None = None
#
#             @event("Confirmed")
#             def confirm(self, at: datetime) -> None:
#                 self.confirmed_at = at
#
#             @event("PickedUp")
#             def pickup(self, at: datetime) -> None:
#                 if self.confirmed_at is None:
#                     msg = "Order is not confirmed"
#                     raise RuntimeError(msg)
#                 self.pickedup_at = at
#
#         order = Order("name")
#         self.assertEqual(len(order.pending_events), 1)
#         with contextlib.suppress(RuntimeError):
#             order.pickup(datetime_now_with_tzinfo())
#         self.assertEqual(len(order.pending_events), 1)
#
#     def test_aggregate_has_a_created_event_name_defined_with_event_decorator(
#         self,
#     ) -> None:
#         class MyAggregate(Aggregate):
#             @event("Started")
#             def __init__(self) -> None:
#                 pass
#
#         a = MyAggregate()
#         created_event = a.pending_events[0]
#         created_event_cls = type(created_event)
#         self.assertEqual(created_event_cls.__name__, "Started")
#
#         self.assertTrue(created_event_cls.__qualname__.endswith("MyAggregate.Started")
#         )
#         self.assertTrue(issubclass(created_event_cls, AggregateCreated))
#         self.assertEqual(created_event_cls, MyAggregate.Started)  # type: ignore[attr-
#         defined]
#
#     def test_decorated_init_has_id_arg(self) -> None:
#         class Index(Aggregate):
#             @event("Started")
#             def __init__(self, id: UUID, name: str):
#                 self._id = id
#                 self.name = name
#
#             @staticmethod
#             def create_id(name: str) -> UUID:
#                 return uuid5(NAMESPACE_URL, f"/pages/{name}")
#
#         name = "name"
#         index_id = Index.create_id(name)
#         index = Index(name=name, id=index_id)
#         self.assertEqual(index.id, index_id)
#
#     def test_one_of_many_created_events_selected_by_init_method_decorator(self) -> Non
#     e:
#         class MyAggregate(Aggregate):
#             class Started(AggregateCreated):
#                 pass
#
#             class Opened(AggregateCreated):
#                 pass
#
#             @event(Started)
#             def __init__(self) -> None:
#                 pass
#
#         a = MyAggregate()
#         created_event = a.pending_events[0]
#         created_event_cls = type(created_event)
#         self.assertEqual(created_event_cls.__name__, "Started")
#         self.assertTrue(created_event_cls.__qualname__.endswith("MyAggregate.Started")
#         )
#         self.assertTrue(issubclass(created_event_cls, AggregateCreated))
#         self.assertEqual(created_event_cls, MyAggregate.Started)
#
#     def test_aggregate_has_incompatible_created_event_class_in_event_decorator(
#         self,
#     ) -> None:
#         # Event mentions 'a' but constructor doesn't.
#         class MyAggregate1(Aggregate):
#             class Started(AggregateCreated):
#                 a: int
#
#             @event(Started)
#             def __init__(self) -> None:
#                 pass
#
#         with self.assertRaises(TypeError) as cm:
#             MyAggregate1()
#
#         # Check error message.
#         errmsg = cm.exception.args[0]
#         self.assertTrue(
#             errmsg.startswith(
#                 f"Unable to construct '{MyAggregate1.Started.__qualname__}' event:"
#             ),
#             errmsg,
#         )
#         self.assertTrue(
#             errmsg.endswith("__init__() missing 1 required keyword-only argument: 'a'"
#             ),
#             errmsg,
#         )
#
#         with self.assertRaises(TypeError) as cm:
#             MyAggregate1(a=1)  # type: ignore[call-arg]
#
#         method_name = get_method_name(MyAggregate1.__init__)
#         self.assertEqual(
#             f"{method_name}() got an unexpected keyword argument 'a'",
#             cm.exception.args[0],
#         )
#
#         # Constructor mentions 'a' but event doesn't.
#         class MyAggregate2(Aggregate):
#             class Started(AggregateCreated):
#                 pass
#
#             @event(Started)
#             def __init__(self, a: int):
#                 self.a = a
#
#         with self.assertRaises(TypeError) as cm:
#             MyAggregate2()  # type: ignore[call-arg]
#
#         # Check error message.
#         method_name = get_method_name(MyAggregate2.__init__)
#         self.assertEqual(
#             f"{method_name}() missing 1 required positional argument: 'a'",
#             cm.exception.args[0],
#         )
#
#         # agg = MyAggregate2(a=1)
#         # self.assertEqual(agg.a, 1)
#         # return
#
#         with self.assertRaises(TypeError) as cm:
#             MyAggregate2(a=1)
#         errmsg = cm.exception.args[0]
#         self.assertTrue(
#             errmsg.startswith(
#                 f"Unable to construct '{MyAggregate2.Started.__qualname__}' event:"
#             ),
#             errmsg,
#         )
#         self.assertTrue(
#             errmsg.endswith("__init__() got an unexpected keyword argument 'a'"),
#             errmsg,
#         )
#
#     def test_raises_if_given_event_class_on_command_method_can_init_aggregate(
#         self,
#     ) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class MyAggregate(Aggregate):
#                 @event(Aggregate.Created)
#                 def do_something(self) -> None:
#                     pass
#
#         self.assertIn("is subclass of CanInit", cm.exception.args[0])
#
#     def test_raises_if_given_event_class_on_command_method_is_not_aggregate_event(
#         self,
#     ) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class X:
#                 pass
#
#             class MyAggregate(Aggregate):
#                 @event(X)  # type: ignore[call-arg, type-var]
#                 def do_something(self) -> None:
#                     pass
#
#         self.assertIn(
#             "is not a str, function, property, or subclass of CanMutateAggregate",
#             cm.exception.args[0],
#         )
#
#     def test_raises_if_decorated_method_has_positional_only_args(
#         self,
#     ) -> None:
#         # TODO: Actually support this.
#         with self.assertRaises(TypeError) as cm:
#
#             class MyAggregate(Aggregate):
#                 @event
#                 def do_something(self, x: int, /) -> None:
#                     pass
#
#             a = MyAggregate()
#             a.do_something(1)
#
#         self.assertIn(
#             (
#                 "positional only args arg not supported by "
#                 "@event decorator on do_something(): x"
#             ),
#             cm.exception.args[0],
#         )
#
#     def test_decorated_method_has_original_docstring(self) -> None:
#         class MyAggregate(Aggregate):
#             def method0(self) -> None:
#                 """Method 0"""
#
#             @event
#             def method1(self) -> None:
#                 """Method 1"""
#
#         self.assertEqual(MyAggregate.method0.__doc__, "Method 0")
#         self.assertEqual(MyAggregate().method0.__doc__, "Method 0")
#         self.assertEqual(MyAggregate.method1.__doc__, "Method 1")
#         self.assertEqual(MyAggregate().method1.__doc__, "Method 1")
#
#     def test_decorated_method_has_original_annotations(self) -> None:
#         class MyAggregate(Aggregate):
#             def method0(self, a: int) -> None:
#                 """Method 0"""
#
#             @event
#             def method1(self, a: int) -> None:
#                 """Method 1"""
#
#         expected_annotations = {"a": "int", "return": "None"}
#         self.assertEqual(MyAggregate.method0.__annotations__, expected_annotations)
#         self.assertEqual(MyAggregate().method0.__annotations__, expected_annotations)
#         self.assertEqual(MyAggregate.method1.__annotations__, expected_annotations)
#         self.assertEqual(MyAggregate().method1.__annotations__, expected_annotations)
#
#     def test_decorated_method_has_original_module(self) -> None:
#         class MyAggregate(Aggregate):
#             def method0(self, a: int) -> None:
#                 """Method 0"""
#
#             @event
#             def method1(self, a: int) -> None:
#                 """Method 1"""
#
#         expected_module = __name__
#         self.assertEqual(MyAggregate.method0.__module__, expected_module)
#         self.assertEqual(MyAggregate().method0.__module__, expected_module)
#         self.assertEqual(MyAggregate.method1.__module__, expected_module)
#         self.assertEqual(MyAggregate().method1.__module__, expected_module)
#
#     def test_decorated_method_has_original_name(self) -> None:
#         class MyAggregate(Aggregate):
#             def method0(self, a: int) -> None:
#                 """Method 0"""
#
#             @event
#             def method1(self, a: int) -> None:
#                 """Method 1"""
#
#         self.assertEqual(MyAggregate.method0.__name__, "method0")
#         self.assertEqual(MyAggregate().method0.__name__, "method0")
#         self.assertEqual(MyAggregate.method1.__name__, "method1")
#         self.assertEqual(MyAggregate().method1.__name__, "method1")
#
#     # def test_raises_when_apply_method_returns_value(self) -> None:
#     #     # Different name.
#     #     class MyAgg(Aggregate):
#     #         @event("EventName")
#     #         def name(self) -> None:
#     #             return 1
#     #
#     #     a = MyAgg()
#     #
#     #     with self.assertRaises(TypeError) as cm:
#     #         a.name()
#     #     msg = str(cm.exception.args[0])
#     #     self.assertTrue(msg.startswith("Unexpected value returned from "), msg)
#     #     self.assertTrue(
#     #         msg.endswith(
#     #             "MyAgg.name(). Values returned from 'apply' methods are discarded."
#     #         ),
#     #         msg,
#     #     )
#     def test_can_include_timestamp_in_command_method_signature(self) -> None:
#         class Order(Aggregate):
#             def __init__(self, name: str, timestamp: datetime | None = None) -> None:
#                 self.name = name
#                 self.confirmed_at: datetime | None = None
#                 self.pickedup_at: datetime | None = None
#
#             class Started(AggregateCreated):
#                 name: str
#
#             @event("Confirmed")
#             def confirm(self, timestamp: datetime | None = None) -> None:
#                 self.confirmed_at = timestamp
#
#             class PickedUp(Aggregate.Event):
#                 pass
#
#             @event(PickedUp)
#             def picked_up(self, timestamp: datetime | None = None) -> None:
#                 self.pickedup_at = timestamp
#
#         order1 = Order("order1")
#         self.assertIsInstance(order1.created_on, datetime)
#         order1.confirm()
#         self.assertIsInstance(order1.modified_on, datetime)
#         self.assertGreater(order1.modified_on, order1.created_on)
#
#         order2 = Order(
#             "order2", timestamp=datetime(year=2000, month=1, day=1, tzinfo=UTC)
#         )
#         self.assertIsInstance(order2.created_on, datetime)
#         self.assertEqual(order2.created_on.year, 2000)
#         self.assertEqual(order2.created_on.month, 1)
#         self.assertEqual(order2.created_on.day, 1)
#
#         order2.confirm(timestamp=datetime(year=2000, month=1, day=2, tzinfo=UTC))
#         self.assertIsInstance(order2.created_on, datetime)
#         self.assertEqual(order2.modified_on.year, 2000)
#         self.assertEqual(order2.modified_on.month, 1)
#         self.assertEqual(order2.modified_on.day, 2)
#         self.assertEqual(order2.confirmed_at, order2.modified_on)
#
#         order2.picked_up(timestamp=datetime(year=2000, month=1, day=3, tzinfo=UTC))
#         self.assertIsInstance(order2.created_on, datetime)
#         self.assertEqual(order2.modified_on.year, 2000)
#         self.assertEqual(order2.modified_on.month, 1)
#         self.assertEqual(order2.modified_on.day, 3)
#         self.assertEqual(order2.pickedup_at, order2.modified_on)
#
#     def test_raises_when_decorated_mentions_non_nested_class(self) -> None:
#         with self.assertRaises(TypeError):
#
#             class Something(AggregateEvent):
#                 pass
#
#             class Order(Aggregate):
#                 @event(Something)
#                 def do(self) -> None:
#                     pass
#
#
# class TestOrder(TestCase):
#     def test(self) -> None:
#         class OrderConfirmedError(Exception):
#             pass
#
#         class Order(Aggregate):
#             def __init__(self, name: str) -> None:
#                 self.name = name
#                 self.confirmed_at: datetime | None = None
#                 self.pickedup_at: datetime | None = None
#
#             class Started(AggregateCreated):
#                 name: str
#
#             @event("Confirmed")
#             def confirm(self, at: datetime) -> None:
#                 self.confirmed_at = at
#
#             def pickup(self, at: datetime) -> None:
#                 if self.confirmed_at:
#                     self._pickup(at)
#                 else:
#                     msg = "Order is not confirmed"
#                     raise OrderConfirmedError(msg)
#
#             @event("Pickedup")
#             def _pickup(self, at: datetime) -> None:
#                 self.pickedup_at = at
#
#         order = Order("my order")
#         self.assertEqual(order.name, "my order")
#
#         with self.assertRaises(OrderConfirmedError) as cm:
#             order.pickup(datetime_now_with_tzinfo())
#         self.assertEqual(cm.exception.args[0], "Order is not confirmed")
#
#         self.assertEqual(order.confirmed_at, None)
#         self.assertEqual(order.pickedup_at, None)
#
#         order.confirm(datetime_now_with_tzinfo())
#         self.assertIsInstance(order.confirmed_at, datetime)
#         self.assertEqual(order.pickedup_at, None)
#
#         order.pickup(datetime_now_with_tzinfo())
#         self.assertIsInstance(order.confirmed_at, datetime)
#         self.assertIsInstance(order.pickedup_at, datetime)
#
#         # Check the events determine the state correctly.
#         pending_events = order.collect_events()
#         copy = Order.__new__(Order)
#         for e in pending_events:
#             copy = e.mutate(copy)
#
#         assert isinstance(copy, Order)
#         self.assertEqual(copy.name, order.name)
#         self.assertEqual(copy.created_on, order.created_on)
#         self.assertEqual(copy.modified_on, order.modified_on)
#         self.assertEqual(copy.confirmed_at, order.confirmed_at)
#         self.assertEqual(copy.pickedup_at, order.pickedup_at)
