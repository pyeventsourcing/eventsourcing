from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest import TestCase
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from eventsourcing.domain import (
    Aggregate,
    AggregateCreated,
    AggregateEvent,
    BaseAggregate,
    OriginatorIDError,
    OriginatorVersionError,
    datetime_now_with_tzinfo,
)
from eventsourcing.tests.domain import (
    AccountClosedError,
    BankAccount,
    InsufficientFundsError,
)
from eventsourcing.utils import get_method_name


class TestMetaAggregate(TestCase):
    def test_aggregate_class_has_a_created_event_class(self) -> None:
        a = Aggregate()
        created_event = a._pending_events[0]
        self.assertIs(type(created_event), Aggregate.Created)

    def test_aggregate_subclass_is_a_dataclass_iff_decorated_or_has_annotations(
        self,
    ) -> None:
        self.assertFalse("__dataclass_fields__" in Aggregate.__dict__)

        # No dataclass decorator, no annotations.
        class MyAggregateWithoutDecorator(Aggregate):
            pass

        self.assertFalse("__dataclass_fields__" in MyAggregateWithoutDecorator.__dict__)

        # Has a dataclass decorator but no annotations.
        @dataclass
        class MyAggregateWithDecorator(Aggregate):
            pass

        self.assertTrue("__dataclass_fields__" in MyAggregateWithDecorator.__dict__)

        # Has annotations but no decorator.
        class MyAggregate(Aggregate):
            a: int

        self.assertTrue("__dataclass_fields__" in MyAggregate.__dict__)

    def test_aggregate_subclass_gets_a_default_created_event_class(self) -> None:
        class MyAggregate(Aggregate):
            pass

        a = MyAggregate()
        created_event = a._pending_events[0]
        self.assertIs(type(created_event), MyAggregate.Created)

    def test_aggregate_subclass_has_a_custom_created_event_class(self) -> None:
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

        a = MyAggregate()
        created_event = a._pending_events[0]
        self.assertIs(type(created_event), MyAggregate.Started)

    def test_aggregate_subclass_has_a_custom_created_event_class_name(self) -> None:
        @dataclass
        class MyAggregate(Aggregate, created_event_name="Started"):
            pass

        a = MyAggregate()
        created_event = a._pending_events[0]
        self.assertIs(type(created_event), MyAggregate.Started)  # type: ignore[attr-defined]
        self.assertTrue(
            type(created_event).__qualname__.endswith("MyAggregate.Started")
        )

    def test_can_define_initial_version_number(self) -> None:
        # Set on BaseAggregate class.
        original_initial_version = BaseAggregate.INITIAL_VERSION
        assert original_initial_version != 0
        try:
            BaseAggregate.INITIAL_VERSION = 0
            self.assertEqual(Aggregate().version, 0)
        finally:
            BaseAggregate.INITIAL_VERSION = original_initial_version

        # Set on Aggregate class.
        original_initial_version = BaseAggregate.INITIAL_VERSION
        assert "INITIAL_VERSION" not in Aggregate.__dict__
        try:
            Aggregate.INITIAL_VERSION = 0
            self.assertEqual(Aggregate().version, 0)
        finally:
            del Aggregate.INITIAL_VERSION

        # Set on subclass.
        class MyAggregate1(Aggregate):
            INITIAL_VERSION = 0

        a1 = MyAggregate1()
        self.assertEqual(a1.version, 0)

        class MyAggregate2(Aggregate):
            pass

        a2 = MyAggregate2()
        self.assertEqual(a2.version, 1)

        class MyAggregate3(Aggregate):
            INITIAL_VERSION = 2

        a3 = MyAggregate3()
        self.assertEqual(a3.version, 2)


class TestAggregateCreation(TestCase):
    def test_call_class_method_create(self) -> None:
        # Check the _create() method creates a new aggregate.
        before_created = datetime_now_with_tzinfo()
        aggregate_id = uuid4()
        a = Aggregate._create(
            event_class=AggregateCreated,
            id=aggregate_id,
        )
        after_created = datetime_now_with_tzinfo()
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.id, aggregate_id)
        self.assertEqual(a.version, 1)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertGreater(a.created_on, before_created)
        self.assertGreater(after_created, a.created_on)

    def test_raises_when_call_class_method_create_with_invalid_id(self) -> None:
        # Check the _create() method creates a new aggregate.
        aggregate_id = Decimal("15.15")
        with self.assertRaises(TypeError) as cm:
            Aggregate._create(
                event_class=AggregateCreated,
                id=aggregate_id,  # type: ignore[arg-type]
            )
        self.assertEqual(
            cm.exception.args[0],
            "Given id was not a UUID or str: Decimal('15.15')",
        )

    def test_raises_when_create_args_mismatch_created_event(self) -> None:
        class BrokenAggregate(Aggregate):
            @classmethod
            def create(cls, name: str) -> BrokenAggregate:
                return cls._create(event_class=cls.Created, id=uuid4(), name=name)

        with self.assertRaises(TypeError) as cm:
            BrokenAggregate.create("name")

        method_name = get_method_name(BrokenAggregate.Created.__init__)

        self.assertEqual(
            f"Unable to construct '{BrokenAggregate.Created.__qualname__}' event: "
            f"{method_name}() got an unexpected keyword argument 'name'",
            cm.exception.args[0],
        )

    def test_call_base_class(self) -> None:
        before_created = datetime_now_with_tzinfo()
        a = Aggregate()
        after_created = datetime_now_with_tzinfo()
        self.assertIsInstance(a, Aggregate)
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertGreater(a.created_on, before_created)
        self.assertGreater(after_created, a.created_on)

        events = a.collect_events()
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual("Aggregate.Created", type(events[0]).__qualname__)

    def test_call_subclass_with_no_init(self) -> None:
        qualname = type(self).__qualname__
        prefix = f"{qualname}.test_call_subclass_with_no_init.<locals>."

        class MyAggregate1(Aggregate):
            pass

        a1 = MyAggregate1()
        self.assertIsInstance(a1.id, UUID)
        self.assertIsInstance(a1.version, int)
        self.assertEqual(a1.version, 1)
        self.assertIsInstance(a1.created_on, datetime)
        self.assertIsInstance(a1.modified_on, datetime)

        events = a1.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate1.Created", type(events[0]).__qualname__)

        # Do it again using @dataclass
        @dataclass  # ...this just makes the code completion work in the IDE.
        class MyAggregate2(Aggregate):
            pass

        # Check the init method takes no args (except "self").
        init_params = inspect.signature(MyAggregate2.__init__).parameters
        self.assertEqual(len(init_params), 1)
        self.assertEqual(next(iter(init_params)), "self")

        #
        # Do it again with custom "created" event.
        @dataclass
        class MyAggregate3(Aggregate):
            class Started(AggregateCreated):
                pass

        a3 = MyAggregate3()
        self.assertIsInstance(a3.id, UUID)
        self.assertIsInstance(a3.version, int)
        self.assertIsInstance(a3.created_on, datetime)
        self.assertIsInstance(a3.modified_on, datetime)

        events = a3.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate3.Started", type(events[0]).__qualname__)

    def test_init_no_args(self) -> None:
        qualname = type(self).__qualname__
        prefix = f"{qualname}.test_init_no_args.<locals>."

        class MyAggregate1(Aggregate):
            def __init__(self) -> None:
                pass

        a1 = MyAggregate1()
        self.assertIsInstance(a1.id, UUID)
        self.assertIsInstance(a1.version, int)
        self.assertIsInstance(a1.created_on, datetime)
        self.assertIsInstance(a1.modified_on, datetime)

        events = a1.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate1.Created", type(events[0]).__qualname__)

        #
        # Do it again using @dataclass (makes no difference)...
        @dataclass  # ...this just makes the code completion work in the IDE.
        class MyAggregate2(Aggregate):
            def __init__(self) -> None:
                pass

        # Check the init method takes no args (except "self").
        init_params = inspect.signature(MyAggregate2.__init__).parameters
        self.assertEqual(len(init_params), 1)
        self.assertEqual(next(iter(init_params)), "self")

        #
        # Do it again with custom "created" event.
        @dataclass
        class MyAggregate3(Aggregate):
            class Started(AggregateCreated):
                pass

        a3 = MyAggregate3()
        self.assertIsInstance(a3.id, UUID)
        self.assertIsInstance(a3.version, int)
        self.assertIsInstance(a3.created_on, datetime)
        self.assertIsInstance(a3.modified_on, datetime)

        events = a3.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate3.Started", type(events[0]).__qualname__)

    def test_raises_when_init_with_no_args_called_with_args(self) -> None:
        # First, with a normal dataclass, to document the errors.
        @dataclass
        class Data(Aggregate):
            pass

        # Second, with an aggregate class, to replicate same errors.
        @dataclass
        class MyAgg(Aggregate):
            pass

        def assert_raises(cls: type[Data | MyAgg]) -> None:
            method_name = get_method_name(cls.__init__)

            with self.assertRaises(TypeError) as cm:
                cls(0)  # type: ignore[call-arg]

            self.assertEqual(
                cm.exception.args[0],
                f"{method_name}() takes 1 positional argument but 2 were given",
            )

            with self.assertRaises(TypeError) as cm:
                cls(value=0)  # type: ignore[call-arg]

            self.assertEqual(
                cm.exception.args[0],
                f"{method_name}() got an unexpected keyword argument 'value'",
            )

        assert_raises(Data)
        assert_raises(MyAgg)

    def test_init_defined_with_positional_or_keyword_arg(self) -> None:
        class MyAgg(Aggregate):
            def __init__(self, value: int) -> None:
                self.value = value

        a = MyAgg(1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

        a = MyAgg(value=1)
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

    def test_init_defined_with_default_keyword_arg(self) -> None:
        class MyAgg(Aggregate):
            def __init__(self, value: int = 0) -> None:
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 0)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

    def test_init_with_default_keyword_arg_required_positional_and_keyword_only(
        self,
    ) -> None:
        class MyAgg(Aggregate):
            def __init__(self, a: int, b: int = 0, *, c: Any) -> None:
                self.a = a
                self.b = b
                self.c = c

        x = MyAgg(1, c=2)
        self.assertEqual(x.a, 1)
        self.assertEqual(x.b, 0)
        self.assertEqual(x.c, 2)

    def test_raises_when_init_missing_1_required_positional_arg(self) -> None:
        class MyAgg(Aggregate):
            def __init__(self, value: Any) -> None:
                self.value = value

        with self.assertRaises(TypeError) as cm:
            MyAgg()  # type: ignore[call-arg]

        self.assertEqual(
            cm.exception.args[0],
            f"{get_method_name(MyAgg.__init__)}() missing 1 required "
            "positional argument: 'value'",
        )

    def test_raises_when_init_missing_1_required_keyword_only_arg(self) -> None:
        class MyAgg(Aggregate):
            def __init__(self, *, value: Any) -> None:
                self.value = value

        with self.assertRaises(TypeError) as cm:
            MyAgg()  # type: ignore[call-arg]

        self.assertEqual(
            cm.exception.args[0],
            f"{get_method_name(MyAgg.__init__)}() missing 1 required "
            "keyword-only argument: 'value'",
        )

    def test_raises_when_init_missing_required_positional_and_keyword_only_arg(
        self,
    ) -> None:
        class MyAgg1(Aggregate):
            def __init__(self, a: Any, *, b: Any) -> None:
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg1()  # type: ignore[call-arg]

        method_name = get_method_name(MyAgg1.__init__)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() missing 1 required positional argument: 'a'",
        )

        class MyAgg2(Aggregate):
            def __init__(self, a: Any, b: int = 0, *, c: Any) -> None:
                self.a = a
                self.b = b
                self.c = c

        with self.assertRaises(TypeError) as cm:
            MyAgg2(c=2)  # type: ignore[call-arg]

        method_name = get_method_name(MyAgg2.__init__)
        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() missing 1 required positional argument: 'a'",
        )

    def test_raises_when_init_missing_2_required_positional_args(self) -> None:
        class MyAgg(Aggregate):
            def __init__(self, a: Any, b: Any, *, c: Any) -> None:
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg()  # type: ignore[call-arg]

        method_name = get_method_name(MyAgg.__init__)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() missing 2 required positional arguments: 'a' and 'b'",
        )

    def test_raises_when_init_gets_unexpected_keyword_argument(self) -> None:
        class MyAgg(Aggregate):
            def __init__(self, a: int = 1) -> None:
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg(b=1)  # type: ignore[call-arg]

        method_name = get_method_name(MyAgg.__init__)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() got an unexpected keyword argument 'b'",
        )

        with self.assertRaises(TypeError) as cm:
            MyAgg(c=1)  # type: ignore[call-arg]

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() got an unexpected keyword argument 'c'",
        )

        with self.assertRaises(TypeError) as cm:
            MyAgg(b=1, c=1)  # type: ignore[call-arg]

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() got an unexpected keyword argument 'b'",
        )

    def test_init_defined_as_dataclass_no_default(self) -> None:
        class MyAgg(Aggregate):
            value: int

        a = MyAgg(1)  # type: ignore[call-arg]
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

        a = MyAgg(value=1)  # type: ignore[call-arg]
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

    def test_init_defined_as_dataclass_with_default(self) -> None:
        class MyAgg(Aggregate):
            value: int = 0

        a = MyAgg(1)  # type: ignore[call-arg]
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

        a = MyAgg(value=1)  # type: ignore[call-arg]
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 1)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 0)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

        with self.assertRaises(TypeError) as cm:
            MyAgg(wrong=1)  # type: ignore[call-arg]

        method_name = get_method_name(MyAgg.__init__)

        self.assertEqual(
            f"{method_name}() got an unexpected keyword argument 'wrong'",
            cm.exception.args[0],
        )

    def test_init_defined_as_dataclass_mixture_of_nondefault_and_default_values(
        self,
    ) -> None:
        @dataclass
        class MyAgg(Aggregate):
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

        def test_init(cls: type[MyAgg | Data]) -> None:
            obj = cls(b=1, a=2)
            self.assertEqual(obj.a, 2)
            self.assertEqual(obj.b, 1)
            self.assertEqual(obj.c, 1)
            self.assertEqual(obj.d, 2)

            obj = cls(1, 2, 3, 4)
            self.assertEqual(obj.a, 1)
            self.assertEqual(obj.b, 2)
            self.assertEqual(obj.c, 3)
            self.assertEqual(obj.d, 4)

            with self.assertRaises(TypeError) as cm:
                obj = cls(1, 2, 3, c=4)  # type: ignore[misc]
                self.assertEqual(obj.a, 1)
                self.assertEqual(obj.b, 2)
                self.assertEqual(obj.c, 4)
                self.assertEqual(obj.d, 3)

            method_name = get_method_name(cls.__init__)

            self.assertEqual(
                f"{method_name}() got multiple values for argument 'c'",
                cm.exception.args[0],
            )

            with self.assertRaises(TypeError) as cm:
                obj = cls(1, a=2, d=3, c=4)  # type: ignore[call-arg, misc]
                self.assertEqual(obj.a, 2)
                self.assertEqual(obj.b, 1)
                self.assertEqual(obj.c, 4)
                self.assertEqual(obj.d, 3)

            self.assertEqual(
                f"{method_name}() got multiple values for argument 'a'",
                cm.exception.args[0],
            )

        test_init(Data)
        test_init(MyAgg)

    def test_raises_when_init_has_variable_positional_params(self) -> None:
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):  # noqa: N801
                def __init__(self, *values: Any) -> None:
                    pass

        self.assertEqual(
            cm.exception.args[0], "*values not supported by decorator on __init__()"
        )

    def test_raises_when_init_has_variable_keyword_params(self) -> None:
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):  # noqa: N801
                def __init__(self, **values: Any) -> None:
                    pass

        self.assertEqual(
            cm.exception.args[0], "**values not supported by decorator on __init__()"
        )

    def test_define_custom_create_id_as_uuid5(self) -> None:
        class MyAggregate1(Aggregate):
            def __init__(self, name: str) -> None:
                self.name = name

            @classmethod
            def create_id(cls, name: str) -> UUID:
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        a1 = MyAggregate1("name")
        self.assertEqual(a1.name, "name")
        self.assertEqual(a1.id, MyAggregate1.create_id("name"))

        # Do it again with method defined as staticmethod.
        @dataclass
        class MyAggregate2(Aggregate):
            name: str

            @staticmethod
            def create_id(name: str) -> UUID:
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        a2 = MyAggregate2("name")
        self.assertEqual(a2.name, "name")
        self.assertEqual(a2.id, MyAggregate2.create_id("name"))

    def test_raises_type_error_if_create_id_does_not_return_uuid_or_str(
        self,
    ) -> None:
        # Returning an int is not okay.
        class MyAggregate1(Aggregate):
            @staticmethod
            def create_id() -> int:  # type: ignore[override]
                return 5

        with self.assertRaises(TypeError) as cm:
            MyAggregate1()

        self.assertIn("create_id did not return UUID or str", str(cm.exception))

        class MyAggregate2(Aggregate):
            def __init__(self, name: str) -> None:
                self.name = name

            @staticmethod
            def create_id(name: str) -> UUID:
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        MyAggregate2(name="name")

        # Create string ID, which is okay until the domain event is constructed.
        # TODO: Maybe aggregate could find aggregateID type arg in its __orig_bases__?
        class MyAggregate3(Aggregate):
            def __init__(self, name: str) -> None:
                self.name = name

            @staticmethod
            def create_id(name: str) -> str:  # type: ignore[override]
                return str(uuid5(NAMESPACE_URL, f"/names/{name}"))

        with self.assertRaises(TypeError) as cm:
            MyAggregate3(name="name")

        self.assertIn(
            "was initialized with a non-UUID originator_id",
            str(cm.exception),
        )

    def test_raises_type_error_if_create_id_not_staticmethod_or_classmethod(
        self,
    ) -> None:
        with self.assertRaises(TypeError):

            class MyAggregate(Aggregate):
                def create_id(self, myarg: str) -> UUID:  # type: ignore[override]
                    return uuid4()

    def test_created_event_name_class_arg(self) -> None:
        # __init__ method has no args
        class MyAggregate1(Aggregate, created_event_name="Opened"):
            pass

        a1 = MyAggregate1()
        self.assertEqual(type(a1.pending_events[0]).__name__, "Opened")

        # __init__ method has one arg
        class MyAggregate2(Aggregate, created_event_name="Opened"):
            def __init__(self, name: str) -> None:
                self.name = name

        a2 = MyAggregate2("peter")
        self.assertEqual(a2.name, "peter")
        self.assertEqual(type(a2.pending_events[0]).__name__, "Opened")

        # dataclass __init__ method has one arg
        class MyAggregate3(Aggregate, created_event_name="Opened"):
            name: str

        a3 = MyAggregate3("peter")  # type: ignore[call-arg]
        self.assertEqual(a3.name, "peter")
        self.assertEqual(type(a3.pending_events[0]).__name__, "Opened")

        class Rabbit(Aggregate, created_event_name="Born"):
            name: str

        # Create a new aggregate.
        rabbit = Rabbit("peter")  # type: ignore[call-arg]

        # The created event class name is "Born".
        assert isinstance(
            rabbit.pending_events[0],
            Rabbit.Born,  # type: ignore[attr-defined]
        )
        self.assertEqual(rabbit.name, "peter")

    def test_refuse_implicit_choice_of_alternative_created_events(self) -> None:
        # In case aggregates were created with old Created event,
        # there may need to be several defined. Then, when calling
        # aggregate class, require explicit statement of which to use.

        # Don't specify created event class.
        class MyAggregate1(Aggregate):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

        # This is okay.
        MyAggregate1._create(event_class=MyAggregate1.Started)
        MyAggregate1._create(event_class=MyAggregate1.Opened)

        with self.assertRaises(TypeError) as cm:
            # This is not okay.
            MyAggregate1()

        self.assertEqual(
            f"{MyAggregate1.__qualname__} can't decide which of many "
            '"created" event classes to '
            "use: 'Started', 'Opened'. "
            "Please use class arg 'created_event_name' or "
            "@event decorator on __init__ method.",
            cm.exception.args[0],
        )

        # Specify created event class using created_event_name.
        class MyAggregate3(Aggregate, created_event_name="Started"):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

        # Call class, and expect Started event will be used.
        a3 = MyAggregate3()
        events = a3.collect_events()
        self.assertIsInstance(events[0], MyAggregate3.Started)

    def test_refuse_implicit_choice_of_alternative_created_events_on_subclass(
        self,
    ) -> None:
        # In case aggregates were created with old Created event,
        # there may need to be several defined. Then, when calling
        # aggregate class, require explicit statement of which to use.
        class MyBaseAggregate(Aggregate, created_event_name="Opened"):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

        class MyAggregate1(MyBaseAggregate):
            class Started(  # pyright: ignore [reportIncompatibleVariableOverride]
                AggregateCreated
            ):
                pass

            class Opened(  # pyright: ignore [reportIncompatibleVariableOverride]
                AggregateCreated
            ):
                pass

        # This is okay.
        MyAggregate1._create(event_class=MyAggregate1.Started)
        MyAggregate1._create(event_class=MyAggregate1.Opened)

        with self.assertRaises(TypeError) as cm:
            MyAggregate1()  # This is not okay.

        self.assertTrue(
            cm.exception.args[0].startswith(
                f"{MyAggregate1.__qualname__} can't decide which of many "
                '"created" event classes to '
                "use: 'Started', 'Opened'"
            )
        )

    def test_uses_defined_created_event_when_given_name_matches(self) -> None:
        class Order(BaseAggregate, created_event_name="Started"):
            def __init__(self, name: str) -> None:
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            @staticmethod
            def create_id() -> UUID:
                return uuid4()

            class Event(AggregateEvent):
                pass

            class Created(AggregateCreated):
                name: str

            class Started(AggregateCreated):
                name: str

        order = Order("name")
        pending = order.collect_events()
        self.assertEqual(type(pending[0]).__name__, "Started")

    def test_define_create_id(self) -> None:
        @dataclass
        class Index(Aggregate):
            name: str

            @staticmethod
            def create_id(name: str) -> UUID:
                return uuid5(NAMESPACE_URL, f"/pages/{name}")

        index = Index(name="name")
        self.assertEqual(index.name, "name")
        self.assertEqual(index.id, Index.create_id("name"))

    def test_id_dataclass_style(self) -> None:
        @dataclass
        class MyDataclass:
            id: UUID
            name: str

        @dataclass
        class Index(Aggregate):
            id: UUID  # pyright: ignore [reportIncompatibleMethodOverride]
            name: str

            @staticmethod
            def create_id(name: str) -> UUID:
                return uuid5(NAMESPACE_URL, f"/pages/{name}")

        def assert_id_dataclass_style(cls: type[MyDataclass | Index]) -> None:
            with self.assertRaises(TypeError) as cm:
                cls()  # type: ignore[call-arg]
            self.assertEqual(
                cm.exception.args[0],
                f"{get_method_name(cls.__init__)}() missing 2 "
                "required positional arguments: 'id' and 'name'",
            )

            # Just check it works if used properly.
            name = "name"
            index_id = Index.create_id(name)
            obj = cls(name=name, id=index_id)
            self.assertEqual(obj.id, index_id)
            self.assertEqual(obj.id, index_id)

        assert_id_dataclass_style(MyDataclass)
        assert_id_dataclass_style(Index)

    def test_init_has_id_arg(self) -> None:
        class Index(Aggregate):
            def __init__(self, id: UUID, name: str):  # noqa: A002
                self._id = id
                self.name = name

            @staticmethod
            def create_id(name: str) -> UUID:
                return uuid5(NAMESPACE_URL, f"/pages/{name}")

        name = "name"
        index_id = Index.create_id(name)
        index = Index(name=name, id=index_id)
        self.assertEqual(index.id, index_id)


class TestSubsequentEvents(TestCase):
    def test_trigger_event(self) -> None:
        a = Aggregate()

        # Check the aggregate can trigger further events.
        a.trigger_event(AggregateEvent)
        self.assertLess(a.created_on, a.modified_on)

        pending = a.collect_events()
        self.assertEqual(len(pending), 2)
        self.assertIsInstance(pending[0], AggregateCreated)
        self.assertEqual(pending[0].originator_version, 1)
        self.assertIsInstance(pending[1], AggregateEvent)
        self.assertEqual(pending[1].originator_version, 2)

    def test_event_mutate_raises_originator_version_error(self) -> None:
        a = Aggregate()

        # Try to mutate aggregate with an invalid domain event.
        event = AggregateEvent(
            originator_id=a.id,
            originator_version=a.version,  # NB not +1.
        )
        # Check raises "VersionError".
        with self.assertRaises(OriginatorVersionError):
            event.mutate(a)

    def test_event_mutate_raises_originator_id_error(self) -> None:
        a = Aggregate()

        # Try to mutate aggregate with an invalid domain event.
        event = AggregateEvent(
            originator_id=uuid4(),
            originator_version=a.version + 1,
        )
        # Check raises "VersionError".
        with self.assertRaises(OriginatorIDError):
            event.mutate(a)

    def test_raises_when_triggering_event_with_mismatched_args(self) -> None:
        class MyAgg(Aggregate):
            @classmethod
            def create(cls) -> MyAgg:
                return cls._create(event_class=cls.Created, id=uuid4())

            class ValueUpdated(AggregateEvent):
                a: int

        a = MyAgg.create()

        with self.assertRaises(TypeError) as cm:
            a.trigger_event(MyAgg.ValueUpdated)
        self.assertTrue(
            cm.exception.args[0].startswith("Can't construct event"),
            cm.exception.args[0],
        )
        self.assertTrue(
            cm.exception.args[0].endswith(
                "__init__() missing 1 required keyword-only argument: 'a'"
            ),
            cm.exception.args[0],
        )

    # def test_raises_when_apply_method_returns_value(self) -> None:
    #     class MyAgg(Aggregate):
    #         class ValueUpdated(AggregateEvent):
    #             a: int
    #
    #             def apply(self, aggregate: TAggregate) -> None:
    #                 return 1
    #
    #     a = MyAgg()
    #     with self.assertRaises(TypeError) as cm:
    #         a.trigger_event(MyAgg.ValueUpdated, a=1)
    #     msg = str(cm.exception.args[0])
    #
    #     self.assertTrue(msg.startswith("Unexpected value returned from "), msg)
    #     self.assertTrue(
    #         msg.endswith(
    #             "MyAgg.ValueUpdated.apply(). Values returned from 'apply' methods are"
    #             " discarded."
    #         ),
    #         msg,
    #     )

    def test_eq(self) -> None:
        class MyAggregate1(Aggregate):
            id: UUID  # pyright: ignore [reportIncompatibleMethodOverride]

        id_a = uuid4()
        id_b = uuid4()
        a1 = MyAggregate1(id=id_a)  # type: ignore[call-arg]
        self.assertEqual(a1, a1)

        b1 = MyAggregate1(id=id_b)  # type: ignore[call-arg]
        self.assertNotEqual(a1, b1)

        c1 = MyAggregate1(id=id_a)  # type: ignore[call-arg]
        self.assertNotEqual(a1, c1)

        a1_copy = a1.collect_events()[0].mutate(None)
        self.assertEqual(a1, a1_copy)

        # Check the aggregate can trigger further events.
        a1.trigger_event(AggregateEvent)
        self.assertNotEqual(a1, a1_copy)
        a1.collect_events()
        self.assertNotEqual(a1, a1_copy)

        @dataclass
        class MyAggregate2(Aggregate):
            id: UUID  # pyright: ignore [reportIncompatibleMethodOverride]

        id_a = uuid4()
        id_b = uuid4()
        a2 = MyAggregate2(id=id_a)
        self.assertEqual(a2, a2)

        b2 = MyAggregate2(id=id_b)
        self.assertNotEqual(a2, b2)

        c2 = MyAggregate2(id=id_a)
        self.assertNotEqual(a2, c2)

        a2_copy = a2.collect_events()[0].mutate(None)
        self.assertEqual(a2, a2_copy)

        # Check the aggregate can trigger further events.
        a2.trigger_event(AggregateEvent)
        self.assertNotEqual(a2, a2_copy)
        a2.collect_events()
        self.assertNotEqual(a2, a2_copy)

    def test_repr_baseclass(self) -> None:
        a = Aggregate()

        expect = (
            f"Aggregate(id={a.id!r}, "
            "version=1, "
            f"created_on={a.created_on!r}, "
            f"modified_on={a.modified_on!r}"
            ")"
        )
        self.assertEqual(expect, repr(a))

        a.trigger_event(AggregateEvent)

        expect = (
            f"Aggregate(id={a.id!r}, "
            "version=2, "
            f"created_on={a.created_on!r}, "
            f"modified_on={a.modified_on!r}"
            ")"
        )
        self.assertEqual(expect, repr(a))

    def test_repr_subclass(self) -> None:
        class MyAggregate1(Aggregate):
            a: int

            class ValueAssigned(AggregateEvent):
                b: int

                def apply(self, aggregate: MyAggregate1) -> None:
                    aggregate.b = self.b  # type: ignore[attr-defined]

        a1 = MyAggregate1(a=1)  # type: ignore[call-arg]
        expect = (
            f"MyAggregate1(id={a1.id!r}, "
            "version=1, "
            f"created_on={a1.created_on!r}, "
            f"modified_on={a1.modified_on!r}, "
            "a=1"
            ")"
        )
        self.assertEqual(expect, repr(a1))

        a1.trigger_event(MyAggregate1.ValueAssigned, b=2)

        expect = (
            f"MyAggregate1(id={a1.id!r}, "
            "version=2, "
            f"created_on={a1.created_on!r}, "
            f"modified_on={a1.modified_on!r}, "
            "a=1, "
            "b=2"
            ")"
        )
        self.assertEqual(expect, repr(a1))

        @dataclass(repr=False)
        class MyAggregate2(Aggregate):
            a: int

            class ValueAssigned(AggregateEvent):
                b: int

                def apply(self, aggregate: MyAggregate2) -> None:
                    aggregate.b = self.b  # type: ignore[attr-defined]

        a2 = MyAggregate2(a=1)
        expect = (
            f"MyAggregate2(id={a2.id!r}, "
            "version=1, "
            f"created_on={a2.created_on!r}, "
            f"modified_on={a2.modified_on!r}, "
            "a=1"
            ")"
        )
        self.assertEqual(expect, repr(a2))

        a2.trigger_event(MyAggregate2.ValueAssigned, b=2)

        expect = (
            f"MyAggregate2(id={a2.id!r}, "
            "version=2, "
            f"created_on={a2.created_on!r}, "
            f"modified_on={a2.modified_on!r}, "
            "a=1, "
            "b=2"
            ")"
        )
        self.assertEqual(expect, repr(a2))


class TestAggregateEventsAreSubclassed(TestCase):
    def test_base_event_class_is_defined_if_missing(self) -> None:
        class MyAggregate(Aggregate):
            pass

        self.assertTrue(MyAggregate.Event.__qualname__.endswith("MyAggregate.Event"))
        self.assertTrue(issubclass(MyAggregate.Event, Aggregate.Event))
        self.assertNotEqual(MyAggregate.Event, Aggregate.Event)

        self.assertTrue(
            MyAggregate.Created.__qualname__.endswith("MyAggregate.Created")
        )
        self.assertTrue(issubclass(MyAggregate.Created, Aggregate.Event))
        self.assertTrue(issubclass(MyAggregate.Created, Aggregate.Created))
        self.assertNotEqual(MyAggregate.Created, Aggregate.Created)

    def test_base_event_class_is_not_redefined_if_exists(self) -> None:
        class MyAggregate(Aggregate):
            class Event(Aggregate.Event):
                pass

            my_event_cls = Event

        self.assertTrue(MyAggregate.Event.__qualname__.endswith("MyAggregate.Event"))
        self.assertTrue(issubclass(MyAggregate.Event, Aggregate.Event))
        self.assertNotEqual(MyAggregate.Event, Aggregate.Event)

        self.assertTrue(
            MyAggregate.Created.__qualname__.endswith("MyAggregate.Created")
        )
        self.assertTrue(issubclass(MyAggregate.Created, Aggregate.Event))
        self.assertTrue(issubclass(MyAggregate.Created, Aggregate.Created))
        self.assertNotEqual(MyAggregate.Created, Aggregate.Created)

    def test_user_defined_aggregate_events_are_subclassed(self) -> None:
        class MyAggregate(Aggregate):
            class Created(Aggregate.Created):
                pass

            class Started(Aggregate.Created):
                pass

            class Ended(Aggregate.Event):
                pass

        self.assertTrue(MyAggregate.Event.__qualname__.endswith("MyAggregate.Event"))
        self.assertTrue(issubclass(MyAggregate.Event, Aggregate.Event))
        self.assertNotEqual(MyAggregate.Event, Aggregate.Event)

        self.assertTrue(
            MyAggregate.Created.__qualname__.endswith("MyAggregate.Created")
        )
        self.assertTrue(issubclass(MyAggregate.Created, Aggregate.Event))
        self.assertTrue(issubclass(MyAggregate.Created, Aggregate.Created))
        self.assertNotEqual(MyAggregate.Created, Aggregate.Created)

        self.assertTrue(MyAggregate.Event.__qualname__.endswith("MyAggregate.Event"))
        self.assertTrue(issubclass(MyAggregate.Created, MyAggregate.Event))
        self.assertTrue(issubclass(MyAggregate.Started, MyAggregate.Event))
        self.assertTrue(issubclass(MyAggregate.Ended, MyAggregate.Event))

        class MySubclass(MyAggregate):
            class Opened(MyAggregate.Started):
                pass

        self.assertTrue(MySubclass.Event.__qualname__.endswith("MySubclass.Event"))
        self.assertTrue(MySubclass.Created.__qualname__.endswith("MySubclass.Created"))
        self.assertTrue(
            MySubclass.Started.__qualname__.endswith("MySubclass.Started"),
            MySubclass.Started.__qualname__,
        )
        self.assertTrue(
            MySubclass.Ended.__qualname__.endswith("MySubclass.Ended"),
            MySubclass.Ended.__qualname__,
        )

        ssc = MySubclass()
        created_event = ssc._pending_events[0]
        self.assertTrue(
            type(created_event).__qualname__.endswith("MySubclass.Opened"),
            type(created_event).__qualname__,
        )

        class MySubSubclass(MySubclass):
            pass

        self.assertTrue(
            MySubSubclass.Event.__qualname__.endswith("MySubSubclass.Event")
        )
        self.assertTrue(
            MySubSubclass.Created.__qualname__.endswith("MySubSubclass.Created")
        )
        self.assertTrue(
            MySubSubclass.Started.__qualname__.endswith("MySubSubclass.Started"),
            MySubSubclass.Started.__qualname__,
        )
        self.assertTrue(
            MySubSubclass.Ended.__qualname__.endswith("MySubSubclass.Ended"),
            MySubSubclass.Ended.__qualname__,
        )

        ssc = MySubSubclass()
        created_event = ssc._pending_events[0]

        self.assertTrue(
            type(created_event).__qualname__.endswith("MySubSubclass.Opened"),
            type(created_event).__qualname__,
        )


class TestBankAccount(TestCase):
    def test_subclass_bank_account(self) -> None:
        # Open an account.
        account: BankAccount = BankAccount.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check the created_on.
        self.assertEqual(account.created_on, account.modified_on)

        # Check the initial balance.
        self.assertEqual(account.balance, 0)

        # Credit the account.
        account.append_transaction(Decimal("10.00"))

        # Check the modified_on time was updated.
        assert account.created_on < account.modified_on

        # Check the balance.
        self.assertEqual(account.balance, Decimal("10.00"))

        # Credit the account again.
        account.append_transaction(Decimal("10.00"))

        # Check the balance.
        self.assertEqual(account.balance, Decimal("20.00"))

        # Debit the account.
        account.append_transaction(Decimal("-15.00"))

        # Check the balance.
        self.assertEqual(account.balance, Decimal("5.00"))

        # Fail to debit account (insufficient funds).
        with self.assertRaises(InsufficientFundsError):
            account.append_transaction(Decimal("-15.00"))

        # Increase the overdraft limit.
        account.set_overdraft_limit(Decimal("100.00"))

        # Debit the account.
        account.append_transaction(Decimal("-15.00"))

        # Check the balance.
        self.assertEqual(account.balance, Decimal("-10.00"))

        # Close the account.
        account.close()

        # Fail to debit account (account closed).
        with self.assertRaises(AccountClosedError):
            account.append_transaction(Decimal("-15.00"))

        # Collect pending events.
        pending = account.collect_events()
        self.assertEqual(len(pending), 7)


class TestAggregateSubclass(TestCase):
    def test_subclasses_no_attrs(self) -> None:
        @dataclass
        class A(Aggregate):
            pass

        @dataclass
        class B(A):
            pass

        B()

    def test_subclasses_one_attr(self) -> None:
        @dataclass
        class A(Aggregate):
            a: int

        @dataclass
        class B(A):
            pass

        with self.assertRaises(TypeError):
            B()  # type: ignore[call-arg]

        B(a=1)


class TestAggregateSubclassWithFieldInitFalse(TestCase):
    def test_without_decorator_default_value_set_post_init(self) -> None:
        class A(Aggregate):
            a: int

        class B(A):
            b: bool = field(init=False)

            def __post_init__(self) -> None:
                self.b = False

            def set_b(self) -> None:
                self.b = True

        class C(B):
            c: str

        a = A(a=1)  # type: ignore[call-arg]
        self.assertEqual(a.a, 1)

        b = B(a=1)  # type: ignore[call-arg]
        self.assertEqual(b.a, 1)
        self.assertEqual(b.b, False)

        b.set_b()
        self.assertEqual(b.b, True)

        c = C(a=1, c="c")  # type: ignore[call-arg]
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, False)
        self.assertEqual(c.c, "c")
        c.set_b()
        self.assertEqual(c.b, True)

    def test_without_decorator_default_value_set_on_field(self) -> None:
        class A(Aggregate):
            a: int

        class B(A):
            b: bool = field(init=False, default=False)

            def set_b(self) -> None:
                self.b = True

        class C(B):
            c: str

        a = A(a=1)  # type: ignore[call-arg]
        self.assertEqual(a.a, 1)

        b = B(a=1)  # type: ignore[call-arg]
        self.assertEqual(b.a, 1)
        self.assertEqual(b.b, False)

        b.set_b()
        self.assertEqual(b.b, True)

        c = C(a=1, c="c")  # type: ignore[call-arg]
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, False)
        self.assertEqual(c.c, "c")
        c.set_b()
        self.assertEqual(c.b, True)

    def test_with_decorator_default_value_set_post_init(self) -> None:
        @dataclass
        class A(Aggregate):
            a: int

        @dataclass
        class B(A):
            b: bool = field(init=False)

            def __post_init__(self) -> None:
                self.b = False

            def set_b(self) -> None:
                self.b = True

        @dataclass
        class C(B):
            c: str

        a = A(a=1)
        self.assertEqual(a.a, 1)

        b = B(a=1)
        self.assertEqual(b.a, 1)
        self.assertEqual(b.b, False)
        b.set_b()
        self.assertEqual(b.b, True)

        c = C(a=1, c="c")
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, False)
        self.assertEqual(c.c, "c")
        c.set_b()
        self.assertEqual(c.b, True)

    def test_with_decorator_default_value_set_on_field(self) -> None:
        @dataclass
        class A:
            a: bool = field(init=False, default=False)

            def set_a(self) -> None:
                self.a = True

        @dataclass
        class B(A):
            b: str

        a = A()
        self.assertFalse(a.a)

        a.set_a()
        self.assertTrue(a.a)

        b = B(b="1")
        self.assertFalse(b.a)
        self.assertEqual(b.b, "1")

        b.set_a()
        self.assertTrue(b.a)

    def test_with_decorator_default_value_set_on_field_on_subclass(self) -> None:
        @dataclass
        class A(Aggregate):
            a: int

        @dataclass
        class B(A):
            b: bool = field(init=False, default=False)

            def set_b(self) -> None:
                self.b = True

        @dataclass
        class C(B):
            c: str

        a = A(a=1)
        self.assertEqual(a.a, 1)

        b = B(a=1)
        self.assertEqual(b.a, 1)
        self.assertEqual(b.b, False)

        b.set_b()
        self.assertEqual(b.b, True)

        c = C(a=1, c="c")
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, False)
        self.assertEqual(c.c, "c")
        c.set_b()
        self.assertEqual(c.b, True)


class TestDemoNonidempotentDataclassBehaviour(TestCase):
    def test_single_decorator_default_value_set_post_init(self) -> None:
        @dataclasses.dataclass
        class A:
            a: int

        @dataclasses.dataclass
        class B(A):
            b: bool = field(init=False)

            def __post_init__(self) -> None:
                self.b = False

            def set_b(self) -> None:
                self.b = True

        @dataclasses.dataclass
        class C(B):
            c: str

        a = A(a=1)
        self.assertEqual(a.a, 1)

        b = B(a=1)
        self.assertEqual(b.a, 1)
        self.assertEqual(b.b, False)

        b.set_b()
        self.assertEqual(b.b, True)

        c = C(a=1, c="c")
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, False)
        self.assertEqual(c.c, "c")
        c.set_b()
        self.assertEqual(c.b, True)

    def test_double_decorator_default_set_post_init(self) -> None:
        # Fails with missing positional argument.

        @dataclasses.dataclass
        @dataclasses.dataclass
        class A:
            a: int

        @dataclasses.dataclass
        @dataclasses.dataclass
        class B(A):
            b: bool = field(init=False)

            def __post_init__(self) -> None:
                self.b = False

            def set_b(self) -> None:
                self.b = True

        @dataclasses.dataclass
        @dataclasses.dataclass
        class C(B):
            c: str

        a = A(a=1)
        self.assertEqual(a.a, 1)

        b = B(a=1)
        self.assertEqual(b.a, 1)
        self.assertEqual(b.b, False)

        b.set_b()
        self.assertEqual(b.b, True)

        with self.assertRaises(TypeError) as cm:
            C(a=1, c="c")

        self.assertIn("missing 1 required positional argument: 'b'", str(cm.exception))

    def test_single_decorator_default_value_set_on_field(self) -> None:
        @dataclasses.dataclass
        class A:
            a: int

        @dataclasses.dataclass
        class B(A):
            b: bool = field(init=False, default=False)

            def set_b(self) -> None:
                self.b = True

        @dataclasses.dataclass
        class C(B):
            c: str

        a = A(a=1)
        self.assertEqual(a.a, 1)

        b = B(a=1)
        self.assertEqual(b.a, 1)
        self.assertEqual(b.b, False)

        b.set_b()
        self.assertEqual(b.b, True)

        c = C(a=1, c="c")
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, False)
        self.assertEqual(c.c, "c")
        c.set_b()
        self.assertEqual(c.b, True)

    def test_double_decorator_default_value_set_on_field(self) -> None:
        @dataclasses.dataclass
        @dataclasses.dataclass
        class A:
            a: int

        @dataclasses.dataclass
        @dataclasses.dataclass
        class B(A):
            b: bool = field(init=False, default=False)

            def set_b(self) -> None:
                self.b = True

        with self.assertRaises(TypeError) as cm:

            @dataclasses.dataclass
            @dataclasses.dataclass
            class C(B):
                c: str

        self.assertIn(
            "non-default argument 'c' follows default argument", str(cm.exception)
        )
