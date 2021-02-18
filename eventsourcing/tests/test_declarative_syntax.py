from dataclasses import dataclass
from datetime import datetime
from unittest import TestCase
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import Application
from eventsourcing.declarative import (
    DecoratableAggregate,
    DecoratedAggregate,
    MetaDecoratableAggregate,
    aggregate,
    event,
    triggers,
)
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

        # Again, with decorator called with no args.
        @aggregate()
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

    def test_init_with_1_default_keyword_arg(self):
        @aggregate
        class MyAgg:
            def __init__(self, value=0):
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 0)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

    def test_init_with_default_keyword_arg_required_positional_and_keyword_only(self):
        @aggregate
        class MyAgg:
            def __init__(self, a, b=0, *, c):
                self.a = a
                self.b = b
                self.c = c

        x = MyAgg(1, c=2)
        self.assertEqual(x.a, 1)
        self.assertEqual(x.b, 0)
        self.assertEqual(x.c, 2)

    def test_raises_when_init_missing_1_required_positional_arg(self):
        @aggregate
        class MyAgg:
            def __init__(self, value):
                self.value = value

        with self.assertRaises(TypeError) as cm:
            MyAgg()
        self.assertEqual(
            cm.exception.args[0],
            "__init__() missing 1 required positional argument: 'value'",
        )

    def test_raises_when_init_missing_1_required_keyword_only_arg(self):
        @aggregate
        class MyAgg:
            def __init__(self, *, value):
                self.value = value

        with self.assertRaises(TypeError) as cm:
            MyAgg()
        self.assertEqual(
            cm.exception.args[0],
            "__init__() missing 1 required keyword-only argument: 'value'",
        )

    def test_raises_when_init_missing_required_positional_and_keyword_only_arg(self):
        @aggregate
        class MyAgg:
            def __init__(self, a, *, b):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg()
        self.assertEqual(
            cm.exception.args[0],
            "__init__() missing 1 required positional argument: 'a'",
        )

        @aggregate
        class MyAgg:
            def __init__(self, a, b=0, *, c):
                self.a = a
                self.b = b
                self.c = c

        with self.assertRaises(TypeError) as cm:
            MyAgg(c=2)
        self.assertEqual(
            cm.exception.args[0],
            "__init__() missing 1 required positional argument: 'a'",
        )

    def test_raises_when_init_missing_2_required_positional_args(self):
        @aggregate
        class MyAgg:
            def __init__(self, a, b, *, c):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg()
        self.assertEqual(
            cm.exception.args[0],
            "__init__() missing 2 required positional arguments: 'a' and 'b'",
        )

    def test_raises_when_init_gets_unexpected_keyword_argument(self):
        @aggregate
        class MyAgg:
            def __init__(self, a=1):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg(b=1)
        self.assertEqual(
            cm.exception.args[0],
            "__init__() got an unexpected keyword argument 'b'",
        )

        with self.assertRaises(TypeError) as cm:
            MyAgg(c=1)
        self.assertEqual(
            cm.exception.args[0],
            "__init__() got an unexpected keyword argument 'c'",
        )

        with self.assertRaises(TypeError) as cm:
            MyAgg(b=1, c=1)
        self.assertEqual(
            cm.exception.args[0],
            "__init__() got an unexpected keyword argument 'b'",
        )

    def test_define_custom_create_id_as_uuid5(self):
        @aggregate
        class MyAgg:
            def __init__(self, name):
                self.name = name

            @classmethod
            def create_id(cls, name):
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        a = MyAgg("name")
        self.assertEqual(a.name, "name")
        self.assertEqual(a.id, MyAgg.create_id("name"))

        # Do it again as a dataclass.
        @aggregate(is_dataclass=True)
        class MyAgg:
            name: str

            @classmethod
            def create_id(cls, name):
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        a = MyAgg("name")
        self.assertEqual(a.name, "name")
        self.assertEqual(a.id, MyAgg.create_id("name"))

        # Do it again as a dataclass (method defined as staticmethod).
        @aggregate(is_dataclass=True)
        class MyAgg:
            name: str

            @staticmethod
            def create_id(name):
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        a = MyAgg("name")
        self.assertEqual(a.name, "name")
        self.assertEqual(a.id, MyAgg.create_id("name"))

    def test_aggregate_on_dataclass_no_defaults(self):
        @aggregate
        @dataclass
        class MyAgg:
            value: int

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

    def test_aggregate_on_dataclass_default_also_passed_to_constructor(self):
        @aggregate
        @dataclass
        class MyAgg:
            value: int = 0

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

    def test_aggregate_on_dataclass_default_value_not_passed_to_constructor(self):
        @aggregate
        @dataclass
        class MyAgg:
            value: int = 0

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 0)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

    def test_aggregate_on_dataclass_mixture_of_default_values(self):
        @aggregate
        @dataclass
        class MyAgg:
            a: int
            b: int
            c: int = 1
            d: int = 2

        # This to check aggregate performs the same behaviour.
        @dataclass
        class Data:
            a: int
            b: int
            c: int = 1
            d: int = 2

        d = Data(b=1, a=2)
        self.assertEqual(d.a, 2)
        self.assertEqual(d.b, 1)
        self.assertEqual(d.c, 1)
        self.assertEqual(d.d, 2)
        x = MyAgg(b=1, a=2)
        self.assertEqual(x.a, 2)
        self.assertEqual(x.b, 1)
        self.assertEqual(x.c, 1)
        self.assertEqual(x.d, 2)

        d = Data(1, 2, 3, 4)
        self.assertEqual(d.a, 1)
        self.assertEqual(d.b, 2)
        self.assertEqual(d.c, 3)
        self.assertEqual(d.d, 4)
        x = MyAgg(1, 2, 3, 4)
        self.assertEqual(x.a, 1)
        self.assertEqual(x.b, 2)
        self.assertEqual(x.c, 3)
        self.assertEqual(x.d, 4)

        with self.assertRaises(TypeError) as cm:
            d = Data(1, 2, 3, c=4)
            self.assertEqual(d.a, 1)
            self.assertEqual(d.b, 2)
            self.assertEqual(d.c, 4)
            self.assertEqual(d.d, 3)
        self.assertEqual(
            cm.exception.args[0], "__init__() got multiple values for argument 'c'"
        )

        with self.assertRaises(TypeError) as cm:
            x = MyAgg(1, 2, 3, c=4)
            self.assertEqual(x.a, 1)
            self.assertEqual(x.b, 2)
            self.assertEqual(x.c, 4)
            self.assertEqual(x.d, 3)
        self.assertEqual(
            cm.exception.args[0], "__init__() got multiple values for argument 'c'"
        )

        with self.assertRaises(TypeError) as cm:
            d = Data(1, a=2, d=3, c=4)
            self.assertEqual(d.a, 2)
            self.assertEqual(d.b, 1)
            self.assertEqual(d.c, 4)
            self.assertEqual(d.d, 3)
        self.assertEqual(
            cm.exception.args[0], "__init__() got multiple values for argument 'a'"
        )
        with self.assertRaises(TypeError) as cm:
            x = MyAgg(1, a=2, d=3, c=4)
            self.assertEqual(x.a, 2)
            self.assertEqual(x.b, 1)
            self.assertEqual(x.c, 4)
            self.assertEqual(x.d, 3)
        self.assertEqual(
            cm.exception.args[0], "__init__() got multiple values for argument 'a'"
        )

    def test_aggregate_is_dataclass(self):
        @aggregate(is_dataclass=True)
        class MyAgg:
            value: int = 0

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 0)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

        a = MyAgg(value=1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a._pending_events), 1)

        with self.assertRaises(TypeError) as cm:
            a = MyAgg(wrong=1)
        self.assertEqual(
            cm.exception.args[0],
            "__init__() got an unexpected keyword argument 'wrong'",
        )

    def test_raises_when_aggregate_is_not_dataclass_but_cls_has_annotations(self):
        @aggregate
        class MyAgg:
            value: int

        with self.assertRaises(TypeError) as cm:
            MyAgg(0)
        self.assertEqual(cm.exception.args[0], "MyAgg() takes no args")

        with self.assertRaises(TypeError) as cm:
            MyAgg(value=1)
        self.assertEqual(cm.exception.args[0], "MyAgg() takes no args")

    def test_raises_when_init_has_variable_positional_params(self):
        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
                def __init__(self, *values):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable positional parameters not supported"
        )

    def test_raises_when_init_has_variable_keyword_params(self):
        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
                def __init__(self, **values):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable keyword parameters not supported"
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

    def test_raises_when_method_takes_1_positional_argument_but_2_were_given(self):
        @aggregate
        class MyAgg:
            @event
            def value_changed(self):
                pass

        class Data:
            def value_changed(self):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
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
        @aggregate
        class MyAgg:
            @event
            def value_changed(self, value):
                pass

        class Data:
            def value_changed(self, value):
                pass

        d = Data()
        with self.assertRaises(TypeError) as cm:
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
        @aggregate
        class MyAgg:
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
        @aggregate
        class MyAgg:
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
        @aggregate
        class MyAgg:
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
        @aggregate
        class MyAgg:
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
        @aggregate
        class MyAgg:
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
        @aggregate
        class MyAgg:
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
        @aggregate
        class MyAgg:
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
        @aggregate
        class MyAgg:
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

            @aggregate
            class MyAgg:
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

            @aggregate
            class MyAgg:
                @event
                @classmethod
                def value_changed(cls):
                    pass

        self.assertEqual(
            cm.exception.args[0],
            "value_changed() classmethod can't be used to update aggregate state",
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
            "@event on value() property setter requires event class name",
        )

    def test_raises_when_property_decorates_event_without_name(self):
        with self.assertRaises(TypeError) as cm:

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
            "@event under value() property setter requires event class name",
        )

    def test_raises_unsupported_usage(self):
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

        @aggregate
        class MyAgg:
            @event("EventName")
            def method(self):
                pass

        with self.assertRaises(ValueError) as cm:
            MyAgg.method()  # called on class (not a bound event)...
        self.assertEqual(
            cm.exception.args[0], "Unsupported usage: event object was called directly"
        )

    def test_raises_when_method_has_args_or_kwargs(self):

        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
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

        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
                @event  # no event name
                def method(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable keyword parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
                @event("EventName")  # no event name
                def method(self, **kwargs):
                    pass

        self.assertEqual(
            cm.exception.args[0], "variable keyword parameters not supported"
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
            cm.exception.args[0], "variable keyword parameters not supported"
        )

        with self.assertRaises(TypeError) as cm:

            @aggregate
            class _:
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

    def test_order_with_app(self) -> None:
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
                    raise Exception("Order is not confirmed")

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

        app = Application()
        app.save(order)

        copy = app.repository.get(order.id)

        self.assertEqual(copy.pickedup_at, order.pickedup_at)

    def test_define_aggregae_with_decoratable_metaclass(self) -> None:
        class Order(metaclass=MetaDecoratableAggregate):
            def __init__(self, name) -> None:
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

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

        order = Order("name")

        self.assertEqual(order.name, "name")
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

        app: Application = Application()
        app.save(order)

        copy = app.repository.get(order.id)

        self.assertEqual(copy.pickedup_at, order.pickedup_at)

        self.assertIsInstance(order, Aggregate)
        self.assertIsInstance(order, Order)
        self.assertIsInstance(copy, Aggregate)
        self.assertIsInstance(copy, Order)

    def test_inherit_from_decoratable_aggregate(self) -> None:
        class Order(DecoratableAggregate):
            def __init__(self, name) -> None:
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

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

        order = Order("name")

        self.assertEqual(order.name, "name")
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

        app: Application = Application()
        app.save(order)

        copy = app.repository.get(order.id)

        self.assertEqual(copy.pickedup_at, order.pickedup_at)

        self.assertIsInstance(order, Aggregate)
        self.assertIsInstance(order, Order)
        self.assertIsInstance(copy, Aggregate)
        self.assertIsInstance(copy, Order)

    def test_define_own_created_event_called_started(self) -> None:
        class Order(DecoratableAggregate):
            def __init__(self, name) -> None:
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            @dataclass(frozen=True)
            class Started(Aggregate.Created):
                name: str

        order = Order("name")
        self.assertEqual(order.name, "name")

        pending = order._pending_events  # type: ignore
        self.assertIsInstance(pending[0], Order.Started)

        app: Application = Application()

        app.save(order)

        copy: Order = app.repository.get(order.id)

        self.assertEqual(copy.name, "name")

        self.assertIsInstance(order, Aggregate)
        self.assertIsInstance(order, Order)
        self.assertIsInstance(copy, Aggregate)
        self.assertIsInstance(copy, Order)

    def test_decorated_and_inherit_aggregagte(self) -> None:
        @aggregate
        class Order(Aggregate):
            def __init__(self, name) -> None:
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            @dataclass(frozen=True)
            class Started(Aggregate.Created):
                name: str

        order = Order("name")
        self.assertEqual(order.name, "name")

        pending = order._pending_events
        self.assertIsInstance(pending[0], Order.Started)

        app: Application = Application()

        app.save(order)

        copy: Order = app.repository.get(order.id)

        self.assertEqual(copy.name, "name")

        self.assertIsInstance(order, Aggregate)
        self.assertIsInstance(order, Order)
        self.assertIsInstance(copy, Aggregate)
        self.assertIsInstance(copy, Order)

    def test_inherit_from_decorated_aggregate_class(self) -> None:
        # Here we just use the @event decorator to trigger events
        # that are applied using the decorated method.
        class Order(DecoratedAggregate):
            def __init__(self, name, **kwargs) -> None:
                super(Order, self).__init__(**kwargs)

                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            @dataclass(frozen=True)
            class Created(DecoratedAggregate.Created):
                name: str

            @dataclass(frozen=True)
            class Confirmed(DecoratedAggregate.Event):
                at: datetime

            @triggers(Confirmed)
            def confirm(self, at):
                self.confirmed_at = at

            def pickup(self, at):
                if self.confirmed_at:
                    self._pickup(at)
                else:
                    raise Exception("Order is not confirmed")

            @dataclass(frozen=True)
            class Pickedup(DecoratedAggregate.Event):
                at: datetime

            @triggers(Pickedup)
            def _pickup(self, at):
                self.pickedup_at = at

        order = Order._create(event_class=Order.Created, name="name")

        self.assertEqual(order.name, "name")
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

        app: Application = Application()
        app.save(order)

        copy = app.repository.get(order.id)

        self.assertEqual(copy.pickedup_at, order.pickedup_at)

        self.assertIsInstance(order, Aggregate)
        self.assertIsInstance(order, Order)
        self.assertIsInstance(copy, Aggregate)
        self.assertIsInstance(copy, Order)

    def test_raises_when_event_class_has_apply_method(self) -> None:
        # Check raises when defining an apply method on an
        # event used in a decorator when aggregate inherits
        # from DecoratedAggregate class.
        with self.assertRaises(TypeError) as cm:

            class _(DecoratedAggregate):
                @dataclass(frozen=True)
                class Confirmed(DecoratedAggregate.Event):
                    def apply(self, aggregate):
                        pass

                @triggers(Confirmed)
                def confirm(self):
                    pass

        self.assertEqual(
            cm.exception.args[0], "Confirmed event class has unexpected apply() method"
        )

    def test_use_aggregate_decorator_with_explicit_event_classes(self) -> None:
        # Here we just use the @event decorator to trigger events
        # that are applied using the decorated method.
        @aggregate
        class Order(DecoratedAggregate):
            @dataclass(frozen=True)
            class Confirmed(DecoratedAggregate.Event):
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

    def test_raises_when_event_class_already_defined(self) -> None:
        # Here we just use the @event decorator to trigger events
        # that are applied using the decorated method.
        with self.assertRaises(TypeError) as cm:

            @aggregate
            class Order(DecoratedAggregate):
                @dataclass(frozen=True)
                class Confirmed(DecoratedAggregate.Event):
                    at: datetime

                @triggers("Confirmed")
                def confirm(self, at):
                    self.confirmed_at = at

        self.assertEqual(
            cm.exception.args[0], "Confirmed event already defined on Order"
        )


# Todo: Put method signature in event decorator, so that args can be mapped to names.
# Todo: Maybe allow __init__ to call super, in which case don't redefine __init__.
