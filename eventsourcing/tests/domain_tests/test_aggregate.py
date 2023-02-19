import inspect
from dataclasses import _DataclassParams, dataclass
from datetime import datetime
from decimal import Decimal
from unittest.case import TestCase
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from eventsourcing.domain import (
    Aggregate,
    AggregateCreated,
    AggregateEvent,
    OriginatorIDError,
    OriginatorVersionError,
    TAggregate,
)
from eventsourcing.tests.domain import (
    AccountClosedError,
    BankAccount,
    InsufficientFundsError,
)
from eventsourcing.utils import get_method_name


class TestMetaAggregate(TestCase):
    def test_aggregate_class_has_a_created_event_class(self):
        self.assertTrue(hasattr(Aggregate, "_created_event_class"))
        self.assertTrue(issubclass(Aggregate._created_event_class, AggregateCreated))
        self.assertEqual(Aggregate._created_event_class, Aggregate.Created)

    def test_aggregate_subclass_is_a_dataclass_iff_decorated_or_has_annotations(self):
        # No dataclass decorator, no annotations.
        class MyAggregate(Aggregate):
            pass

        self.assertFalse("__dataclass_params__" in MyAggregate.__dict__)

        # Has a dataclass decorator (helps IDE know what's going on with annotations).
        @dataclass
        class MyAggregate(Aggregate):
            pass

        self.assertTrue("__dataclass_params__" in MyAggregate.__dict__)
        self.assertIsInstance(MyAggregate.__dataclass_params__, _DataclassParams)
        self.assertFalse(MyAggregate.__dataclass_params__.frozen)

        # Has annotations but no decorator.
        @dataclass
        class MyAggregate(Aggregate):
            a: int

        self.assertTrue("__dataclass_params__" in MyAggregate.__dict__)
        self.assertIsInstance(MyAggregate.__dataclass_params__, _DataclassParams)
        self.assertFalse(MyAggregate.__dataclass_params__.frozen)

    def test_aggregate_subclass_gets_a_default_created_event_class(self):
        class MyAggregate(Aggregate):
            pass

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        self.assertTrue(issubclass(MyAggregate._created_event_class, AggregateCreated))
        self.assertEqual(MyAggregate._created_event_class, MyAggregate.Created)

    def test_aggregate_subclass_has_a_custom_created_event_class(self):
        class MyAggregate(Aggregate):
            class Started(AggregateCreated):
                pass

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        self.assertTrue(issubclass(MyAggregate._created_event_class, AggregateCreated))
        self.assertEqual(MyAggregate._created_event_class, MyAggregate.Started)

    def test_aggregate_subclass_has_a_custom_created_event_class_name(self):
        @dataclass
        class MyAggregate(Aggregate, created_event_name="Started"):
            pass

        a = MyAggregate()
        self.assertEqual(type(a.pending_events[0]).__name__, "Started")

        self.assertTrue(hasattr(MyAggregate, "_created_event_class"))
        created_event_cls = MyAggregate._created_event_class
        self.assertEqual(created_event_cls.__name__, "Started")
        self.assertTrue(created_event_cls.__qualname__.endswith("MyAggregate.Started"))
        self.assertTrue(issubclass(created_event_cls, AggregateCreated))
        self.assertEqual(created_event_cls, MyAggregate.Started)

    def test_can_define_initial_version_number(self):
        class MyAggregate1(Aggregate):
            INITIAL_VERSION = 0

        a = MyAggregate1()
        self.assertEqual(a.version, 0)

        class MyAggregate2(Aggregate):
            pass

        a = MyAggregate2()
        self.assertEqual(a.version, 1)

        class MyAggregate3(Aggregate):
            INITIAL_VERSION = 2

        a = MyAggregate3()
        self.assertEqual(a.version, 2)


class TestAggregateCreation(TestCase):
    def test_call_class_method_create(self):
        # Check the _create() method creates a new aggregate.
        before_created = Aggregate.Event.create_timestamp()
        uuid = uuid4()
        a = Aggregate._create(
            event_class=AggregateCreated,
            id=uuid,
        )
        after_created = Aggregate.Event.create_timestamp()
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(a.id, uuid)
        self.assertEqual(a.version, 1)
        self.assertEqual(a.created_on, a.modified_on)
        self.assertGreater(a.created_on, before_created)
        self.assertGreater(after_created, a.created_on)

    def test_raises_when_create_args_mismatch_created_event(self):
        class BrokenAggregate(Aggregate):
            @classmethod
            def create(cls, name):
                return cls._create(event_class=cls.Created, id=uuid4(), name=name)

        with self.assertRaises(TypeError) as cm:
            BrokenAggregate.create("name")

        method_name = get_method_name(BrokenAggregate.Created.__init__)

        self.assertEqual(
            (
                f"Unable to construct 'Created' event: "
                f"{method_name}() got an unexpected keyword argument 'name'"
            ),
            cm.exception.args[0],
        )

    def test_call_base_class(self):
        before_created = Aggregate.Event.create_timestamp()
        a = Aggregate()
        after_created = Aggregate.Event.create_timestamp()
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

    def test_call_subclass_with_no_init(self):
        qualname = type(self).__qualname__
        prefix = f"{qualname}.test_call_subclass_with_no_init.<locals>."

        class MyAggregate1(Aggregate):
            pass

        a = MyAggregate1()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertEqual(a.version, 1)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
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
        self.assertEqual(list(init_params)[0], "self")

        #
        # Do it again with custom "created" event.
        @dataclass
        class MyAggregate3(Aggregate):
            class Started(AggregateCreated):
                pass

        a = MyAggregate3()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate3.Started", type(events[0]).__qualname__)

    def test_init_no_args(self):
        qualname = type(self).__qualname__
        prefix = f"{qualname}.test_init_no_args.<locals>."

        class MyAggregate1(Aggregate):
            def __init__(self):
                pass

        a = MyAggregate1()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate1.Created", type(events[0]).__qualname__)

        #
        # Do it again using @dataclass (makes no difference)...
        @dataclass  # ...this just makes the code completion work in the IDE.
        class MyAggregate2(Aggregate):
            def __init__(self):
                pass

        # Check the init method takes no args (except "self").
        init_params = inspect.signature(MyAggregate2.__init__).parameters
        self.assertEqual(len(init_params), 1)
        self.assertEqual(list(init_params)[0], "self")

        #
        # Do it again with custom "created" event.
        @dataclass
        class MyAggregate3(Aggregate):
            class Started(AggregateCreated):
                pass

        a = MyAggregate3()
        self.assertIsInstance(a.id, UUID)
        self.assertIsInstance(a.version, int)
        self.assertIsInstance(a.created_on, datetime)
        self.assertIsInstance(a.modified_on, datetime)

        events = a.collect_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AggregateCreated)
        self.assertEqual(f"{prefix}MyAggregate3.Started", type(events[0]).__qualname__)

    def test_raises_when_init_with_no_args_called_with_args(self):
        # First, with a normal dataclass, to document the errors.
        @dataclass
        class Data(Aggregate):
            pass

        # Second, with an aggregate class, to replicate same errors.
        @dataclass
        class MyAgg(Aggregate):
            pass

        def assert_raises(cls):
            method_name = get_method_name(cls.__init__)

            with self.assertRaises(TypeError) as cm:
                cls(0)

            self.assertEqual(
                cm.exception.args[0],
                f"{method_name}() takes 1 positional argument but 2 were given",
            )

            with self.assertRaises(TypeError) as cm:
                cls(value=0)

            self.assertEqual(
                cm.exception.args[0],
                f"{method_name}() got an unexpected keyword argument 'value'",
            )

        assert_raises(Data)
        assert_raises(MyAgg)

    def test_init_defined_with_positional_or_keyword_arg(self):
        class MyAgg(Aggregate):
            def __init__(self, value):
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

    def test_init_defined_with_default_keyword_arg(self):
        class MyAgg(Aggregate):
            def __init__(self, value=0):
                self.value = value

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 0)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

    def test_init_with_default_keyword_arg_required_positional_and_keyword_only(self):
        class MyAgg(Aggregate):
            def __init__(self, a, b=0, *, c):
                self.a = a
                self.b = b
                self.c = c

        x = MyAgg(1, c=2)
        self.assertEqual(x.a, 1)
        self.assertEqual(x.b, 0)
        self.assertEqual(x.c, 2)

    def test_raises_when_init_missing_1_required_positional_arg(self):
        class MyAgg(Aggregate):
            def __init__(self, value):
                self.value = value

        with self.assertRaises(TypeError) as cm:
            MyAgg()

        self.assertEqual(
            cm.exception.args[0],
            f"{get_method_name(MyAgg.__init__)}() missing 1 required "
            "positional argument: 'value'",
        )

    def test_raises_when_init_missing_1_required_keyword_only_arg(self):
        class MyAgg(Aggregate):
            def __init__(self, *, value):
                self.value = value

        with self.assertRaises(TypeError) as cm:
            MyAgg()

        self.assertEqual(
            cm.exception.args[0],
            f"{get_method_name(MyAgg.__init__)}() missing 1 required "
            f"keyword-only argument: 'value'",
        )

    def test_raises_when_init_missing_required_positional_and_keyword_only_arg(self):
        class MyAgg(Aggregate):
            def __init__(self, a, *, b):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg()

        method_name = get_method_name(MyAgg.__init__)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() missing 1 required positional argument: 'a'",
        )

        class MyAgg(Aggregate):
            def __init__(self, a, b=0, *, c):
                self.a = a
                self.b = b
                self.c = c

        with self.assertRaises(TypeError) as cm:
            MyAgg(c=2)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() missing 1 required positional argument: 'a'",
        )

    def test_raises_when_init_missing_2_required_positional_args(self):
        class MyAgg(Aggregate):
            def __init__(self, a, b, *, c):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg()

        method_name = get_method_name(MyAgg.__init__)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() missing 2 required positional arguments: 'a' and 'b'",
        )

    def test_raises_when_init_gets_unexpected_keyword_argument(self):
        class MyAgg(Aggregate):
            def __init__(self, a=1):
                pass

        with self.assertRaises(TypeError) as cm:
            MyAgg(b=1)

        method_name = get_method_name(MyAgg.__init__)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() got an unexpected keyword argument 'b'",
        )

        with self.assertRaises(TypeError) as cm:
            MyAgg(c=1)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() got an unexpected keyword argument 'c'",
        )

        with self.assertRaises(TypeError) as cm:
            MyAgg(b=1, c=1)

        self.assertEqual(
            cm.exception.args[0],
            f"{method_name}() got an unexpected keyword argument 'b'",
        )

    def test_init_defined_as_dataclass_no_default(self):
        class MyAgg(Aggregate):
            value: int

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

    def test_init_defined_as_dataclass_with_default(self):
        class MyAgg(Aggregate):
            value: int = 0

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

        a = MyAgg()
        self.assertIsInstance(a, MyAgg)
        self.assertEqual(a.value, 0)
        self.assertIsInstance(a, Aggregate)
        self.assertEqual(len(a.pending_events), 1)

        with self.assertRaises(TypeError) as cm:
            MyAgg(wrong=1)

        method_name = get_method_name(MyAgg.__init__)

        self.assertEqual(
            f"{method_name}() got an unexpected keyword argument 'wrong'",
            cm.exception.args[0],
        )

    def test_init_defined_as_dataclass_mixture_of_nondefault_and_default_values(self):
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

        def test_init(cls):
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
                obj = cls(1, 2, 3, c=4)
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
                obj = cls(1, a=2, d=3, c=4)
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

    def test_raises_when_init_has_variable_positional_params(self):
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                def __init__(self, *values):
                    pass

        self.assertEqual(
            cm.exception.args[0], "*values not supported by decorator on __init__()"
        )

    def test_raises_when_init_has_variable_keyword_params(self):
        with self.assertRaises(TypeError) as cm:

            class _(Aggregate):
                def __init__(self, **values):
                    pass

        self.assertEqual(
            cm.exception.args[0], "**values not supported by decorator on __init__()"
        )

    def test_define_custom_create_id_as_uuid5(self):
        class MyAggregate1(Aggregate):
            def __init__(self, name):
                self.name = name

            @classmethod
            def create_id(cls, name):
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        a = MyAggregate1("name")
        self.assertEqual(a.name, "name")
        self.assertEqual(a.id, MyAggregate1.create_id("name"))

        # Do it again with method defined as staticmethod.
        @dataclass
        class MyAggregate2(Aggregate):
            name: str

            @staticmethod
            def create_id(name):
                return uuid5(NAMESPACE_URL, f"/names/{name}")

        a = MyAggregate2("name")
        self.assertEqual(a.name, "name")
        self.assertEqual(a.id, MyAggregate2.create_id("name"))

    def test_raises_type_error_if_create_id_not_staticmethod_or_classmethod(self):
        with self.assertRaises(TypeError):

            class MyAggregate(Aggregate):
                def create_id(self, myarg):
                    pass

    def test_raises_type_error_if_created_event_class_not_aggregate_created(self):
        with self.assertRaises(TypeError):

            class MyAggregate(Aggregate):
                _created_event_class = Aggregate.Event

    def test_refuse_implicit_choice_of_alternative_created_events(self):
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

        self.assertTrue(
            cm.exception.args[0].startswith(
                "Can't decide which of many "
                '"created" event classes to '
                "use: 'Started', 'Opened'"
            )
        )

        # Specify created event class using _created_event_class.
        class MyAggregate2(Aggregate):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

            _created_event_class = Started

        # Call class, and expect Started event will be used.
        a = MyAggregate2()
        events = a.collect_events()
        self.assertIsInstance(events[0], MyAggregate2.Started, type(events[0]))

        # Specify created event class using created_event_name.
        class MyAggregate3(Aggregate, created_event_name="Started"):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

        # Call class, and expect Started event will be used.
        a = MyAggregate3()
        events = a.collect_events()
        self.assertIsInstance(events[0], MyAggregate3.Started)

    def test_refuse_implicit_choice_of_alternative_created_events_on_subclass(self):
        # In case aggregates were created with old Created event,
        # there may need to be several defined. Then, when calling
        # aggregate class, require explicit statement of which to use.
        class MyBaseAggregate(Aggregate, created_event_name="Opened"):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

        class MyAggregate1(MyBaseAggregate):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

        # This is okay.
        MyAggregate1._create(event_class=MyAggregate1.Started)
        MyAggregate1._create(event_class=MyAggregate1.Opened)

        with self.assertRaises(TypeError) as cm:
            MyAggregate1()  # This is not okay.

        self.assertTrue(
            cm.exception.args[0].startswith(
                "Can't decide which of many "
                '"created" event classes to '
                "use: 'Started', 'Opened'"
            )
        )

        # Specify created event class using _created_event_class.
        class MyAggregate2(MyBaseAggregate):
            class Started(AggregateCreated):
                pass

            class Opened(AggregateCreated):
                pass

            _created_event_class = Started

        # Call class, and expect Started event will be used.
        a = MyAggregate2()
        events = a.collect_events()
        self.assertIsInstance(events[0], MyAggregate2.Started)

    def test_uses_defined_created_event_when_given_name_matches(self):
        class Order(Aggregate, created_event_name="Started"):
            def __init__(self, name):
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            class Created(AggregateCreated):
                name: str

            class Started(AggregateCreated):
                name: str

        order = Order("name")
        pending = order.collect_events()
        self.assertEqual(type(pending[0]).__name__, "Started")

    def test_defines_created_event_when_given_name_does_not_match(self):
        class Order(Aggregate, created_event_name="Started"):
            def __init__(self, name):
                self.name = name
                self.confirmed_at = None
                self.pickedup_at = None

            class Created(AggregateCreated):
                name: str

        order = Order("name")
        pending = order.collect_events()
        self.assertEqual(type(pending[0]).__name__, "Started")

    def test_raises_when_given_created_event_name_conflicts_with_created_event_class(
        self,
    ):
        with self.assertRaises(TypeError) as cm:

            class Order(Aggregate, created_event_name="Started"):
                def __init__(self, name):
                    self.name = name
                    self.confirmed_at = None
                    self.pickedup_at = None

                class Created(AggregateCreated):
                    name: str

                class Started(AggregateCreated):
                    name: str

                _created_event_class = Created

        self.assertEqual(
            cm.exception.args[0],
            "Can't use both '_created_event_class' and 'created_event_name'",
        )

    def test_define_create_id(self):
        @dataclass
        class Index(Aggregate):
            name: str

            @staticmethod
            def create_id(name: str):
                return uuid5(NAMESPACE_URL, f"/pages/{name}")

        index = Index(name="name")
        self.assertEqual(index.name, "name")
        self.assertEqual(index.id, Index.create_id("name"))

    def test_id_dataclass_style(self):
        @dataclass
        class MyDataclass:
            id: UUID
            name: str

        @dataclass
        class Index(Aggregate):
            id: UUID
            name: str

            @staticmethod
            def create_id(name: str):
                return uuid5(NAMESPACE_URL, f"/pages/{name}")

        def assert_id_dataclass_style(cls):
            with self.assertRaises(TypeError) as cm:
                cls()
            self.assertEqual(
                cm.exception.args[0],
                f"{get_method_name(cls.__init__)}() missing 2 "
                f"required positional arguments: 'id' and 'name'",
            )

            # Just check it works if used properly.
            name = "name"
            index_id = Index.create_id(name)
            obj = cls(name=name, id=index_id)
            self.assertEqual(obj.id, index_id)
            self.assertEqual(obj.id, index_id)

        assert_id_dataclass_style(MyDataclass)
        assert_id_dataclass_style(Index)

    def test_init_has_id_explicitly(self):
        class Index(Aggregate):
            def __init__(self, id: UUID, name: str):
                self._id = id
                self.name = name

            @staticmethod
            def create_id(name: str):
                return uuid5(NAMESPACE_URL, f"/pages/{name}")

        name = "name"
        index_id = Index.create_id(name)
        index = Index(name=name, id=index_id)
        self.assertEqual(index.id, index_id)


class TestSubsequentEvents(TestCase):
    def test_trigger_event(self):
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

    def test_event_mutate_raises_originator_version_error(self):
        a = Aggregate()

        # Try to mutate aggregate with an invalid domain event.
        event = AggregateEvent(
            originator_id=a.id,
            originator_version=a.version,  # NB not +1.
            timestamp=AggregateEvent.create_timestamp(),
        )
        # Check raises "VersionError".
        with self.assertRaises(OriginatorVersionError):
            event.mutate(a)

    def test_event_mutate_raises_originator_id_error(self):
        a = Aggregate()

        # Try to mutate aggregate with an invalid domain event.
        event = AggregateEvent(
            originator_id=uuid4(),
            originator_version=a.version + 1,
            timestamp=AggregateEvent.create_timestamp(),
        )
        # Check raises "VersionError".
        with self.assertRaises(OriginatorIDError):
            event.mutate(a)

    def test_raises_when_triggering_event_with_mismatched_args(self):
        class MyAgg(Aggregate):
            @classmethod
            def create(cls):
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
                "__init__() missing 1 required positional argument: 'a'"
            ),
            cm.exception.args[0],
        )

    # def test_raises_when_apply_method_returns_value(self):
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
    #             "MyAgg.ValueUpdated.apply(). Values returned from 'apply' methods are "
    #             "discarded."
    #         ),
    #         msg,
    #     )

    def test_eq(self):
        class MyAggregate1(Aggregate):
            id: UUID

        id_a = uuid4()
        id_b = uuid4()
        a = MyAggregate1(id=id_a)
        self.assertEqual(a, a)

        b = MyAggregate1(id=id_b)
        self.assertNotEqual(a, b)

        c = MyAggregate1(id=id_a)
        self.assertNotEqual(a, c)

        a_copy = a.collect_events()[0].mutate(None)
        self.assertEqual(a, a_copy)

        # Check the aggregate can trigger further events.
        a.trigger_event(AggregateEvent)
        self.assertNotEqual(a, a_copy)
        a.collect_events()
        self.assertNotEqual(a, a_copy)

        @dataclass(eq=False)
        class MyAggregate2(Aggregate):
            id: UUID

        id_a = uuid4()
        id_b = uuid4()
        a = MyAggregate2(id=id_a)
        self.assertEqual(a, a)

        b = MyAggregate2(id=id_b)
        self.assertNotEqual(a, b)

        c = MyAggregate2(id=id_a)
        self.assertNotEqual(a, c)

        a_copy = a.collect_events()[0].mutate(None)
        self.assertEqual(a, a_copy)

        # Check the aggregate can trigger further events.
        a.trigger_event(AggregateEvent)
        self.assertNotEqual(a, a_copy)
        a.collect_events()
        self.assertNotEqual(a, a_copy)

    def test_repr_baseclass(self):
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

    def test_repr_subclass(self):
        class MyAggregate1(Aggregate):
            a: int

            class ValueAssigned(AggregateEvent):
                b: int

                def apply(self, aggregate: TAggregate) -> None:
                    aggregate.b = self.b

        a = MyAggregate1(a=1)
        expect = (
            f"MyAggregate1(id={a.id!r}, "
            "version=1, "
            f"created_on={a.created_on!r}, "
            f"modified_on={a.modified_on!r}, "
            f"a=1"
            ")"
        )
        self.assertEqual(expect, repr(a))

        a.trigger_event(MyAggregate1.ValueAssigned, b=2)

        expect = (
            f"MyAggregate1(id={a.id!r}, "
            "version=2, "
            f"created_on={a.created_on!r}, "
            f"modified_on={a.modified_on!r}, "
            f"a=1, "
            f"b=2"
            ")"
        )
        self.assertEqual(expect, repr(a))

        @dataclass(repr=False)
        class MyAggregate2(Aggregate):
            a: int

            class ValueAssigned(AggregateEvent):
                b: int

                def apply(self, aggregate: TAggregate) -> None:
                    aggregate.b = self.b

        a = MyAggregate2(a=1)
        expect = (
            f"MyAggregate2(id={a.id!r}, "
            "version=1, "
            f"created_on={a.created_on!r}, "
            f"modified_on={a.modified_on!r}, "
            f"a=1"
            ")"
        )
        self.assertEqual(expect, repr(a))

        a.trigger_event(MyAggregate2.ValueAssigned, b=2)

        expect = (
            f"MyAggregate2(id={a.id!r}, "
            "version=2, "
            f"created_on={a.created_on!r}, "
            f"modified_on={a.modified_on!r}, "
            f"a=1, "
            f"b=2"
            ")"
        )
        self.assertEqual(expect, repr(a))


class TestAggregateEventsAreSubclassed(TestCase):
    def test_base_event_class_is_defined_if_missing(self):
        class MyAggregate(Aggregate):
            pass

        self.assertTrue(MyAggregate.Event.__qualname__.endswith("MyAggregate.Event"))
        self.assertTrue(issubclass(MyAggregate.Event, Aggregate.Event))
        self.assertNotEqual(MyAggregate.Event, Aggregate.Event)

    def test_base_event_class_is_not_redefined_if_exists(self):
        class MyAggregate(Aggregate):
            class Event(Aggregate.Event):
                pass

            my_event_cls = Event

        self.assertTrue(MyAggregate.Event.__qualname__.endswith("MyAggregate.Event"))
        self.assertEqual(MyAggregate.my_event_cls, MyAggregate.Event)

    def test_aggregate_events_are_subclassed(self):
        class MyAggregate(Aggregate):
            class Created(Aggregate.Created):
                pass

            class Started(Aggregate.Created):
                pass

            class Ended(Aggregate.Event):
                pass

            _created_event_class = Started

        self.assertTrue(MyAggregate.Event.__qualname__.endswith("MyAggregate.Event"))
        self.assertTrue(issubclass(MyAggregate.Created, MyAggregate.Event))
        self.assertTrue(issubclass(MyAggregate.Started, MyAggregate.Event))
        self.assertTrue(issubclass(MyAggregate.Ended, MyAggregate.Event))
        self.assertEqual(MyAggregate._created_event_class, MyAggregate.Started)

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


class TestBankAccount(TestCase):
    def test_subclass_bank_account(self):
        # Open an account.
        account: BankAccount = BankAccount.open(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check the created_on.
        assert account.created_on == account.modified_on

        # Check the initial balance.
        assert account.balance == 0

        # Credit the account.
        account.append_transaction(Decimal("10.00"))

        # Check the modified_on time was updated.
        assert account.created_on < account.modified_on

        # Check the balance.
        assert account.balance == Decimal("10.00")

        # Credit the account again.
        account.append_transaction(Decimal("10.00"))

        # Check the balance.
        assert account.balance == Decimal("20.00")

        # Debit the account.
        account.append_transaction(Decimal("-15.00"))

        # Check the balance.
        assert account.balance == Decimal("5.00")

        # Fail to debit account (insufficient funds).
        with self.assertRaises(InsufficientFundsError):
            account.append_transaction(Decimal("-15.00"))

        # Increase the overdraft limit.
        account.set_overdraft_limit(Decimal("100.00"))

        # Debit the account.
        account.append_transaction(Decimal("-15.00"))

        # Check the balance.
        assert account.balance == Decimal("-10.00")

        # Close the account.
        account.close()

        # Fail to debit account (account closed).
        with self.assertRaises(AccountClosedError):
            account.append_transaction(Decimal("-15.00"))

        # Collect pending events.
        pending = account.collect_events()
        assert len(pending) == 7
