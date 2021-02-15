from datetime import datetime
from unittest import TestCase
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.declarative import aggregate, event
from eventsourcing.domain import Aggregate


class TestDeclarativeSyntax(TestCase):
    def test_no_init(self):
        @aggregate
        class MyAgg:
            pass

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertIsInstance(a, Aggregate)
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertEqual(len(a._pending_events), 1)
        self.assertIsInstance(a._pending_events[0], MyAgg.Created)

    def test_init_with_positional_args(self):
        @aggregate
        class MyAgg:
            def __init__(self, value):
                self.value = value

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

    def test_init_with_keyword_arg(self):
        @aggregate
        class MyAgg:
            def __init__(self, value):
                self.value = value

        a = MyAgg(value=1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

    def test_raises_when_init_has_variable_positional_params(self):
        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                def __init__(self, *values):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable positional parameters not supported"
        )

    def test_raises_when_init_has_variable_keyword_params(self):
        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                def __init__(self, **values):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable keyword parameters not supported"
        )

    def test_event_name_inferred_from_method_no_args(self):
        @aggregate
        class MyAgg:
            @event
            def heartbeat(self):
                pass

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.heartbeat()
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.version, 2)
        self.assertEqual(len(a._pending_events), 2)
        self.assertIsInstance(a._pending_events[1], MyAgg.Heartbeat)

    def test_event_name_inferred_from_method_with_arg(self):
        @aggregate
        class MyAgg:
            @event
            def value_changed(self, value):
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.value_changed(1)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.version, 2)
        self.assertEqual(len(a._pending_events), 2)
        self.assertIsInstance(a._pending_events[1], MyAgg.ValueChanged)

    def test_event_name_inferred_from_method_with_kwarg(self):
        @aggregate
        class MyAgg:
            @event
            def value_changed(self, value):
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        a.value_changed(value=1)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 2)
        self.assertIsInstance(a._pending_events[1], MyAgg.ValueChanged)

    # Todo: Support default values?
    # def test_event_name_inferred_from_method_with_default_kwarg(self):
    #     @aggregate
    #     class MyAgg:
    #         @event
    #         def value_changed(self, value=3):
    #             self.value = value
    #
    #     a = MyAgg()
    #     self.assertIsInstance(a, MyAgg)
    #     a.value_changed()
    #     self.assertEqual(a.value, 3)
    #     self.assertIsInstance(a, Aggregate)
    #     self.assertEqual(len(a._pending_events), 2)
    #     self.assertIsInstance(a._pending_events[1], MyAgg.ValueChanged)

    def test_method_called_with_positional_when_defined_with_keyword_only(self):
        @aggregate
        class MyAgg:
            @event
            def value_changed(self, *, value):
                pass

        a = MyAgg()

        with self.assertRaises(TypeError) as cm:
            a.value_changed(1)
        self.assertTrue(
            cm.exception.args[0].startswith("Can't construct event"),
            cm.exception.args[0]
        )

    def test_method_called_with_positional_defined_with_keyword_params(self):
        @aggregate
        class MyAgg:
            @event
            def values_changed(self, a=None, b=None):
                self.a = a
                self.b = b

        a = MyAgg()
        a.values_changed(1, 2)

    def test_method_called_with_keyword_defined_with_positional_params(self):
        @aggregate
        class MyAgg:
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

    def test_raises_when_method_has_positional_only_params(self):
        @aggregate
        class MyAgg:
            @event
            def values_changed(self, a, b, /):
                self.a = a
                self.b = b

        with self.assertRaises(TypeError) as cm:

            a = MyAgg()
            a.values_changed(1, 2)

        # self.assertTrue(cm.exception.args[0].startswith(
        #     "values_changed() got some positional-only arguments"
        # ))

    def test_raises_when_event_called_with_missing_arg(self):
        @aggregate
        class MyAgg:
            @event
            def value_changed(self, value):
                pass

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        with self.assertRaises(TypeError) as cm:
            a.value_changed()
        self.assertTrue(
            cm.exception.args[0].startswith("Can't construct event "),
            cm.exception.args[0]
        )

    def test_event_name_set_in_decorator(self):
        @aggregate
        class MyAgg:
            @event("ValueChanged")
            def set_value(self, value):
                self.value = value

        a = MyAgg()
        a.set_value(value=1)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 2)
        self.assertIsInstance(a._pending_events[1], MyAgg.ValueChanged)

    def test_event_with_name_decorates_property(self):
        @aggregate
        class MyAgg:
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
        self.assertEqual(len(a._pending_events), 2)
        self.assertIsInstance(a._pending_events[1], MyAgg.ValueChanged)

    def test_property_decorates_event_with_name(self):
        @aggregate
        class MyAgg:
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
        self.assertEqual(len(a._pending_events), 2)
        self.assertIsInstance(a._pending_events[1], MyAgg.ValueChanged)


    def test_raises_when_event_decorates_property_getter(self):
        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @event("ValueChanged")
                @property
                def value(self):
                    return None

        self.assertEqual(cm.exception.args[0], "@event can't decorate property getter")

        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @event("ValueChanged")
                @property
                def value(self):
                    return None

        self.assertEqual(cm.exception.args[0], "@event can't decorate property getter")


    def test_raises_when_event_without_name_decorates_property(self):
        with self.assertRaises(ValueError) as cm:
            @aggregate
            class _:
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
            "Can't decorate property without explicit event name"
        )

    def test_raises_when_property_decorates_event_without_name(self):
        with self.assertRaises(ValueError) as cm:
            @aggregate
            class _:
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
            "Can't decorate property without explicit event name"
        )

    def test_raises_unsupported_usage(self):
        with self.assertRaises(ValueError) as cm:
            event(1)
        self.assertEqual(
            cm.exception.args[0],
            "Unsupported usage: <class 'int'> is not a str or a FunctionType"
        )

        with self.assertRaises(ValueError) as cm:
            event("EventName")(1)
        self.assertEqual(
            cm.exception.args[0],
            "Unsupported usage: <class 'int'> is not a str or a FunctionType"
        )

        @aggregate
        class MyAgg:
            @event("EventName")
            def method(self):
                pass

        with self.assertRaises(ValueError) as cm:
            MyAgg.method()  # called on class (not a bound event)...
        self.assertEqual(
            cm.exception.args[0],
            "Unsupported usage: event object was called directly"
        )

    def test_raises_when_method_has_args_or_kwargs(self):

        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @event  # no event name
                def method(self, *args):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable positional parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @event("EventName")  # has event name
                def method(self, *args):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable positional parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @event  # no event name
                def method(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable keyword parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @event("EventName")  # no event name
                def method(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable keyword parameters not supported"
        )

        # With property.
        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @property
                def name(self):
                    return None

                @event("EventName")  # before setter
                @name.setter
                def name(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable keyword parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:
            @aggregate
            class _:
                @property
                def name(self):
                    return None

                @name.setter
                @event("EventName")   # after setter (same as without property)
                def name(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "variable keyword parameters not supported"
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

    def test_order_with_app(self):

        @aggregate
        class Order:
            def __init__(self):
                self.confirmed_at = None
                self.pickedup_at = None

            @event("Confirmed")
            def confirm(self, at):
                self.confirmed_at = at

            def pickup(self, at):
                if self.confirmed_at:
                    self._pickup(at)
                else:
                    raise Exception('Order is not confirmed')

            @event("Pickedup")
            def _pickup(self, at):
                self.pickedup_at = at

        order = Order()
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

        app: Application[Order] = Application()
        app.save(order)

        copy = app.repository.get(order.id)

        self.assertEqual(copy.pickedup_at, order.pickedup_at)


# Todo: Put method signature in event decorator, so that args can be mapped to names.
# Todo: Maybe allow __init__ to call super, in which case don't redefine __init__.

