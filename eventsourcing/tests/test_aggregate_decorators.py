from dataclasses import dataclass
from datetime import datetime
from unittest import TestCase

from eventsourcing.application import Application
from eventsourcing.domain import (
    Aggregate,
    AggregateCreated,
    AggregateEvent,
    aggregate,
    event,
    triggers,
)


class TestAggregateDecorator(TestCase):
    def test_decorate_class_with_no_bases(self):
        @aggregate
        class MyAgg:
            """My doc"""

            a: int

        self.assertTrue(issubclass(MyAgg, Aggregate))
        self.assertTrue(issubclass(MyAgg, MyAgg))
        self.assertTrue(MyAgg.__name__, "MyAgg")
        self.assertTrue(MyAgg.__doc__, "My doc")
        self.assertEqual(MyAgg.__bases__, (Aggregate,))
        self.assertEqual(MyAgg.__annotations__, {"a": int})

        agg = MyAgg(a=1)
        self.assertEqual(agg.a, 1)
        self.assertEqual(len(agg.pending_events), 1)
        self.assertIsInstance(agg, Aggregate)
        self.assertIsInstance(agg, MyAgg)

    def test_decorate_class_with_one_base(self):
        class MyBase:
            "My base doc"

        @aggregate
        class MyAgg(MyBase):
            """My doc"""

            a: int

        self.assertTrue(issubclass(MyAgg, Aggregate))
        self.assertTrue(issubclass(MyAgg, MyAgg))
        self.assertTrue(issubclass(MyAgg, MyBase))
        self.assertTrue(MyAgg.__name__, "MyAgg")
        self.assertTrue(MyAgg.__doc__, "My doc")
        self.assertEqual(MyAgg.__bases__, (MyBase, Aggregate))
        self.assertEqual(MyAgg.__annotations__, {"a": int})

        agg = MyAgg(a=1)
        self.assertEqual(agg.a, 1)
        self.assertEqual(len(agg.pending_events), 1)
        self.assertIsInstance(agg, Aggregate)
        self.assertIsInstance(agg, MyAgg)
        self.assertIsInstance(agg, MyBase)

    def test_decorate_class_with_two_bases(self):
        class MyAbstract(object):
            "My base doc"

        class MyBase(MyAbstract):
            "My base doc"

        @aggregate
        class MyAgg(MyBase):
            """My doc"""

            a: int

        self.assertTrue(issubclass(MyAgg, Aggregate))
        self.assertTrue(issubclass(MyAgg, MyAgg))
        self.assertTrue(issubclass(MyAgg, MyBase))
        self.assertTrue(issubclass(MyAgg, MyAbstract))
        self.assertTrue(MyAgg.__name__, "MyAgg")
        self.assertTrue(MyAgg.__doc__, "My doc")
        self.assertEqual(MyAgg.__bases__, (MyBase, Aggregate))
        self.assertEqual(MyAgg.__annotations__, {"a": int})

        agg = MyAgg(a=1)
        self.assertEqual(agg.a, 1)
        self.assertEqual(len(agg.pending_events), 1)
        self.assertIsInstance(agg, Aggregate)
        self.assertIsInstance(agg, MyAgg)
        self.assertIsInstance(agg, MyBase)
        self.assertIsInstance(agg, MyAbstract)

    def test_raises_when_decorating_aggregate_subclass(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyUnusedLocal
            @aggregate
            class MyAgg(Aggregate):
                pass

        self.assertEqual(cm.exception.args[0], "MyAgg is already an Aggregate")

    def test_aggregate_on_dataclass(self):
        @aggregate
        @dataclass
        class MyAgg:
            value: int

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

    def test_dataclass_on_aggregate(self):
        @dataclass
        @aggregate
        class MyAgg:
            value: int

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

    def test_aggregate_decorator_called_with_create_event_name(self):
        @aggregate(created_event_name="Started")
        class MyAgg:
            value: int

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)
        self.assertEqual(type(a.pending_events[0]).__name__, "Started")


# noinspection PyUnresolvedReferences
class TestEventDecorator(TestCase):
    def test_event_name_inferred_from_method_no_args(self):
        class MyAgg(Aggregate):
            @event
            def heartbeat(self):
                pass

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.heartbeat()
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.version, 2)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.Heartbeat)

    def test_event_decorator_called_without_args(self):
        class MyAgg(Aggregate):
            @event()
            def heartbeat(self):
                pass

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.heartbeat()
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.version, 2)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.Heartbeat)

    def test_event_name_inferred_from_method_with_arg(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, value):
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.value_changed(1)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.version, 2)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)

    def test_event_name_inferred_from_method_with_kwarg(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, value):
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.value_changed(value=1)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)

    def test_event_name_inferred_from_method_with_default_kwarg(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, value=3):
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.value_changed()
        self.assertEqual(a.value, 3)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)

    def test_raises_when_method_takes_1_positional_argument_but_2_were_given(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self):
                pass

        class Data:
            def value_changed(self):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            # noinspection PyArgumentList
            d.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() takes 1 positional argument but 2 were given",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() takes 1 positional argument but 2 were given",
        )

    def test_raises_when_method_takes_2_positional_argument_but_3_were_given(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, value):
                pass

        class Data:
            def value_changed(self, value):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            # noinspection PyArgumentList
            d.value_changed(1, 2)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() takes 2 positional arguments but 3 were given",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed(1, 2)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() takes 2 positional arguments but 3 were given",
        )

    def test_raises_when_method_missing_1_required_positional_argument(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a):
                pass

        class Data:
            def value_changed(self, a):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 1 required positional argument: 'a'",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 1 required positional argument: 'a'",
        )

    def test_raises_when_method_missing_2_required_positional_arguments(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a, b):
                pass

        class Data:
            def value_changed(self, a, b):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 2 required positional arguments: 'a' and 'b'",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 2 required positional arguments: 'a' and 'b'",
        )

    def test_raises_when_method_missing_3_required_positional_arguments(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a, b, c):
                pass

        class Data:
            def value_changed(self, a, b, c):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 3 required positional arguments: 'a', 'b', and 'c'",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 3 required positional arguments: 'a', 'b', and 'c'",
        )

    def test_raises_when_method_missing_1_required_keyword_only_argument(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a, *, b):
                pass

        class Data:
            def value_changed(self, a, *, b):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 1 required keyword-only argument: 'b'",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 1 required keyword-only argument: 'b'",
        )

    def test_raises_when_method_missing_2_required_keyword_only_arguments(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a, *, b, c):
                pass

        class Data:
            def value_changed(self, a, *, b, c):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 2 required keyword-only arguments: 'b' and 'c'",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 2 required keyword-only arguments: 'b' and 'c'",
        )

    def test_raises_when_method_missing_3_required_keyword_only_arguments(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a, *, b, c, d):
                pass

        class Data:
            def value_changed(self, a, *, b, c, d):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 3 required keyword-only arguments: "
            "'b', 'c', and 'd'",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed(1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 3 required keyword-only arguments: "
            "'b', 'c', and 'd'",
        )

    def test_raises_when_missing_positional_and_required_keyword_only_arguments(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a, *, b, c, d):
                pass

        class Data:
            def value_changed(self, a, *, b, c, d):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 1 required positional argument: 'a'",
        )

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed()
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() missing 1 required positional argument: 'a'",
        )

    def test_raises_when_method_gets_unexpected_keyword_argument(self):
        class MyAgg(Aggregate):
            @event
            def value_changed(self, a):
                pass

        class Data:
            def value_changed(self, a):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
            d.value_changed(b=1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() got an unexpected keyword argument 'b'",
        )

        with self.assertRaises(TypeError) as cm:
            d.value_changed(b=1)
        self.assertEqual(
            cm.exception.args[0],
            "value_changed() got an unexpected keyword argument 'b'",
        )

    def test_raises_when_method_is_staticmethod(self):
        with self.assertRaises(TypeError) as cm:

            class MyAgg(Aggregate):
                @event
                @staticmethod
                def value_changed():
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "value_changed() staticmethod can't be used to update aggregate state",
        )

    def test_raises_when_method_is_classmethod(self):
        with self.assertRaises(TypeError) as cm:

            class MyAgg(Aggregate):
                @event
                @classmethod
                def value_changed(cls):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "value_changed() classmethod can't be used to update aggregate state",
        )

    def test_method_called_with_positional_defined_with_keyword_params(self):
        class MyAgg(Aggregate):
            @event
            def values_changed(self, a=None, b=None):
                self.a = a
                self.b = b

        a = MyAgg()
        a.values_changed(1, 2)

    def test_method_called_with_keyword_defined_with_positional_params(self):
        class MyAgg(Aggregate):
            @event
            def values_changed(self, a, b):
                self.a = a
                self.b = b

        a = MyAgg()
        a.values_changed(a=1, b=2)

    # @skipIf(sys.version_info[0:2] < (3, 8), "Positional only params not supported")
    # def test_method_called_with_keyword_defined_with_positional_only(self):
    #     @aggregate
    #     class MyAgg:
    #         @event
    #         def values_changed(self, a, b, /):
    #             self.a = a
    #             self.b = b
    #
    #     a = MyAgg()
    #     a.values_changed(1, 2)

    # def test_raises_when_method_has_positional_only_params(self):
    #     @aggregate
    #     class MyAgg:
    #         @event
    #         def values_changed(self, a, b, /):
    #             self.a = a
    #             self.b = b
    #
    #     with self.assertRaises(TypeError) as cm:
    #
    #         a = MyAgg()
    #         a.values_changed(1, 2)
    #
    #     self.assertTrue(
    #         cm.exception.args[0].startswith(
    #             # "values_changed() got some positional-only arguments"
    #             "Can't construct event"
    #         ),
    #         cm.exception.args[0],
    #     )

    def test_raises_when_decorated_method_called_directly(self):
        class MyAgg(Aggregate):
            @event
            def method(self):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg.method()
        self.assertEqual(
            cm.exception.args[0],
            "Unsupported usage: event object used without instance",
        )

    def test_event_name_set_in_decorator(self):
        class MyAgg(Aggregate):
            @event("ValueChanged")
            def set_value(self, value):
                self.value = value

        a = MyAgg()
        a.set_value(value=1)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)

    def test_event_name_set_in_decorator_cannot_be_empty_string(self):

        with self.assertRaises(ValueError) as cm:

            class MyAgg(Aggregate):
                @event("")
                def set_value(self, value):
                    self.value = value

        self.assertEqual(
            cm.exception.args[0], "Can't use empty string as name of event class"
        )

    def test_event_with_name_decorates_property(self):
        class MyAgg(Aggregate):
            def __init__(self, value):
                self._value = value

            @property
            def value(self):
                return self._value

            @event("ValueChanged")
            @value.setter
            def value(self, value):
                self._value = value

        a = MyAgg(0)
        self.assertEqual(a.value, 0)
        a.value = 1
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)

    def test_property_decorates_event_with_name(self):
        class MyAgg(Aggregate):
            @property
            def value(self):
                return self._value

            @value.setter
            @event("ValueChanged")
            def value(self, value):
                self._value = value

        a = MyAgg()
        a.value = 1
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 2)
        self.assertIsInstance(a.pending_events[1], MyAgg.ValueChanged)

    def test_raises_when_event_decorates_property_getter(self):
        with self.assertRaises(TypeError) as cm:

            class MyAgg(Aggregate):
                @event("ValueChanged")
                @property
                def value(self):
                    return None

        self.assertEqual(
            cm.exception.args[0], "@event can't decorate value() property getter"
        )

        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
                @event("ValueChanged")
                @property
                def value(self):
                    return None

        self.assertEqual(
            cm.exception.args[0], "@event can't decorate value() property getter"
        )

    def test_raises_when_event_without_name_decorates_property(self):
        with self.assertRaises(TypeError) as cm:

            class MyAgg(Aggregate):
                def __init__(self, _):
                    pass

                @property
                def value(self):
                    return None

                @event
                @value.setter
                def value(self, value):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "@event on value() property setter requires event class name",
        )

    def test_raises_when_property_decorates_event_without_name(self):
        with self.assertRaises(TypeError) as cm:

            class MyAgg(Aggregate):
                def __init__(self, _):
                    pass

                @property
                def value(self):
                    return None

                @value.setter
                @event
                def value(self, _):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "@event under value() property setter requires event class name",
        )

    def test_raises_unsupported_usage_when_event_decorator_used_with_wrong_args(self):
        with self.assertRaises(TypeError) as cm:
            event(1)
        self.assertEqual(
            cm.exception.args[0],
            "Unsupported usage: <class 'int'> is not a str or function",
        )

        with self.assertRaises(ValueError) as cm:
            event("EventName")(1)
        self.assertEqual(
            cm.exception.args[0],
            "Unsupported usage: <class 'int'> is not a str or a FunctionType",
        )

        class MyAgg(Aggregate):
            @event("EventName")
            def method(self):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg.method()  # called on class (not a bound event)...
        self.assertEqual(
            cm.exception.args[0],
            "Unsupported usage: event object used without instance",
        )

    def test_raises_when_decorated_method_has_variable_args(self):

        with self.assertRaises(TypeError) as cm:

            class MyAgg(Aggregate):
                @event  # no event name
                def method(self, *args):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable positional parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
                @event("EventName")  # has event name
                def method(self, *args):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable positional parameters not supported"
        )

    # noinspection PyPep8Naming
    def test_raises_when_decorated_method_has_variable_kwargs(self):

        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                @event  # no event name
                def method(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable keyword parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                @event("EventName")  # no event name
                def method(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable keyword parameters not supported"
        )

        # With property.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                @property
                def name(self):
                    return None

                @event("EventName")  # before setter
                @name.setter
                def name(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable keyword parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                @property
                def name(self):
                    return None

                @name.setter
                @event("EventName")  # after setter (same as without property)
                def name(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable keyword parameters not supported"
        )

    # Todo: Somehow deal with custom decorators?
    # def test_custom_decorators(self):
    #
    #     def mydecorator(f):
    #         def g(*args, **kwargs):
    #             f(*args, **kwargs)
    #         return g
    #
    #     @aggregate
    #     class MyAgg:
    #         @event
    #         @mydecorator
    #         def method(self):
    #             raise Exception("Shou")
    #
    #     a = MyAgg()
    #     a.method()
    #

    def test_event_decorator_uses_explicit_event_classes(self) -> None:
        # Here we just use the @event decorator to trigger events
        # that are applied using the decorated method.
        @aggregate
        class Order:
            class Confirmed(AggregateEvent):
                at: datetime

            @triggers(Confirmed)
            def confirm(self, at):
                self.confirmed_at = at

        order = Order()

        order.confirm(datetime.now())
        self.assertIsInstance(order.confirmed_at, datetime)

        app: Application = Application()
        app.save(order)

        copy = app.repository.get(order.id)

        self.assertEqual(copy.confirmed_at, order.confirmed_at)

        self.assertIsInstance(order, Aggregate)
        self.assertIsInstance(order, Order)
        self.assertIsInstance(copy, Aggregate)
        self.assertIsInstance(copy, Order)

    def test_raises_when_event_class_has_apply_method(self) -> None:
        # Check raises when defining an apply method on an
        # event used in a decorator when aggregate inherits
        # from Aggregate class.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                class Confirmed(AggregateEvent):
                    def apply(self, aggregate):
                        pass

                @triggers(Confirmed)
                def confirm(self):
                    pass

        self.assertEqual(
            cm.exception.args[0], "Confirmed event class has unexpected apply() method"
        )

    def test_raises_when_event_class_already_defined(self) -> None:
        # Here we just use the @event decorator to trigger events
        # that are applied using the decorated method.
        with self.assertRaises(TypeError) as cm:

            @aggregate
            class Order(Aggregate):
                class Confirmed(AggregateEvent):
                    at: datetime

                @triggers("Confirmed")
                def confirm(self, at):
                    self.confirmed_at = at

        self.assertEqual(
            cm.exception.args[0], "Confirmed event already defined on Order"
        )

    def test_raises_when_event_class_name_used_twice(self) -> None:
        # Here we make sure the same event class name can't be
        # declared on two decorators.
        with self.assertRaises(TypeError) as cm:

            @aggregate
            class Order(Aggregate):
                @triggers("Confirmed")
                def confirm1(self, at):
                    self.confirmed_at = at

                @triggers("Confirmed")
                def confirm2(self, at):
                    self.confirmed_at = at

        self.assertEqual(
            cm.exception.args[0], "Confirmed event already defined on Order"
        )

    def test_raises_when_event_class_used_twice(self) -> None:
        # Here we make sure the same event class can't be
        # mentioned on two decorators.
        with self.assertRaises(TypeError) as cm:

            @aggregate
            class Order(Aggregate):
                class Confirmed(AggregateEvent):
                    at: datetime

                @triggers(Confirmed)
                def confirm1(self, at):
                    self.confirmed_at = at

                @triggers(Confirmed)
                def confirm2(self, at):
                    self.confirmed_at = at

        self.assertEqual(
            cm.exception.args[0],
            "Confirmed event class used in more than one decorator",
        )

    def test_dirty_style_isnt_so_dirty_after_all(self):
        class Order(Aggregate):
            def __init__(self, name):
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            @event("Confirmed")
            def confirm(self, at):
                self.confirmed_at = at

            @event("PickedUp")
            def pickup(self, at):
                if self.confirmed_at is None:
                    raise RuntimeError("Order is not confirmed")
                else:
                    self.pickedup_at = at

        order = Order("name")
        self.assertEqual(len(order.pending_events), 1)
        try:
            order.pickup(datetime.now())
        except RuntimeError:
            pass
        self.assertEqual(len(order.pending_events), 1)

    def test_aggregate_has_a_created_event_name_defined_with_event_decorator(self):
        class MyAggregate(Aggregate):
            @event("Started")
            def __init__(self):
                pass

        a = MyAggregate()
        self.assertEqual(type(a.pending_events[0]).__name__, "Started")

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        created_event_cls = MyAggregate._created_event_class
        self.assertEqual(created_event_cls.__name__, "Started")
        self.assertTrue(created_event_cls.__qualname__.endswith("MyAggregate.Started"))
        self.assertTrue(issubclass(created_event_cls, AggregateCreated))
        self.assertEqual(created_event_cls, MyAggregate.Started)

    def test_aggregate_has_a_created_event_class_mentioned_event_decorator(self):
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

            @event(Started)
            def __init__(self):
                pass

        a = MyAggregate()
        self.assertEqual(type(a.pending_events[0]).__name__, "Started")

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        created_event_cls = MyAggregate._created_event_class
        self.assertEqual(created_event_cls.__name__, "Started")
        self.assertTrue(created_event_cls.__qualname__.endswith("MyAggregate.Started"))
        self.assertTrue(issubclass(created_event_cls, AggregateCreated))
        self.assertEqual(created_event_cls, MyAggregate.Started)

    def test_aggregate_has_incompatible_created_event_class_in_event_decorator(self):
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                a: int

            @event(Started)
            def __init__(self):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAggregate()
        self.assertTrue(
            cm.exception.args[0].startswith(
                "Unable to construct 'aggregate created' event with class"
            )
        )

        with self.assertRaises(TypeError) as cm:
            MyAggregate(a=1)
        self.assertEqual(
            cm.exception.args[0], "__init__() got an unexpected keyword argument 'a'"
        )

        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

            @event(Started)
            def __init__(self, a: int):
                self.a = a

        with self.assertRaises(TypeError) as cm:
            MyAggregate()
        self.assertEqual(
            cm.exception.args[0],
            "__init__() missing 1 required positional argument: 'a'",
        )

        with self.assertRaises(TypeError) as cm:
            MyAggregate(a=1)
        self.assertTrue(
            cm.exception.args[0].startswith(
                "Unable to construct 'aggregate created' event with class"
            ),
            cm.exception.args[0],
        )

    def test_raises_when_using_created_event_class_and_init_event_decorator(self):
        # Different name.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                _created_event_class = Opened

                @event("Started")
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both '_created_event_class' and __init__ @event decorator",
        )

        # Same name.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                _created_event_class = Opened

                @event("Opened")
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both '_created_event_class' and __init__ @event decorator",
        )

        # Different class.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                _created_event_class = Opened

                @event(Started)
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both '_created_event_class' and __init__ @event decorator",
        )

        # Same class.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                _created_event_class = Opened

                @event(Opened)
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both '_created_event_class' and __init__ @event decorator",
        )

    def test_raises_when_using_created_event_name_and_init_event_decorator(self):
        # Different name.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate, created_event_name="Opened"):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                @event("Started")
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both 'created_event_name' and __init__ @event decorator",
        )

        # Same name.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate, created_event_name="Opened"):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                @event("Opened")
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both 'created_event_name' and __init__ @event decorator",
        )

        # Different class.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate, created_event_name="Opened"):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                @event(Started)
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both 'created_event_name' and __init__ @event decorator",
        )

        # Same class.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate, created_event_name="Opened"):
                class Started(AggregateCreated):
                    a: int

                class Opened(AggregateCreated):
                    a: int

                @event(Opened)
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both 'created_event_name' and __init__ @event decorator",
        )

    def test_raises_when_using_init_event_decorator_without_args(self):
        # Different name.
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                @event
                def __init__(self):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "Neither name nor class given to __init__ @event decorator",
        )


class TestOrder(TestCase):
    def test(self) -> None:
        class Order(Aggregate):
            def __init__(self, name):
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            class Started(AggregateCreated):
                name: str

            @event("Confirmed")
            def confirm(self, at):
                self.confirmed_at = at

            def pickup(self, at):
                if self.confirmed_at:
                    self._pickup(at)
                else:
                    raise Exception("Order is not confirmed")

            @event("Pickedup")
            def _pickup(self, at):
                self.pickedup_at = at

        order = Order("my order")
        self.assertEqual(order.name, "my order")

        with self.assertRaises(Exception) as cm:
            order.pickup(datetime.now())
        self.assertEqual(cm.exception.args[0], "Order is not confirmed")

        self.assertEqual(order.confirmed_at, None)
        self.assertEqual(order.pickedup_at, None)

        order.confirm(datetime.now())
        self.assertIsInstance(order.confirmed_at, datetime)
        self.assertEqual(order.pickedup_at, None)

        order.pickup(datetime.now())
        self.assertIsInstance(order.confirmed_at, datetime)
        self.assertIsInstance(order.pickedup_at, datetime)

        # Check the events determine the state correctly.
        pending_events = order.collect_events()
        copy = None
        for e in pending_events:
            copy = e.mutate(copy)

        self.assertEqual(copy.name, order.name)
        self.assertEqual(copy.created_on, order.created_on)
        self.assertEqual(copy.modified_on, order.modified_on)
        self.assertEqual(copy.confirmed_at, order.confirmed_at)
        self.assertEqual(copy.pickedup_at, order.pickedup_at)
