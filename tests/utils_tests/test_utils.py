from typing import Generic, cast
from unittest import TestCase

from typing_extensions import TypeVar

import eventsourcing
import eventsourcing.domain
from eventsourcing.domain import Aggregate
from eventsourcing.utils import (
    TopicError,
    clear_topic_cache,
    get_topic,
    register_topic,
    resolve_multi_generic_target,
    resolve_topic,
    retry,
    strtobool,
)


class TestRetryDecorator(TestCase):
    def test_bare(self) -> None:
        @retry  # type: ignore[arg-type]
        def f() -> None:
            pass

        f()  # type: ignore[call-arg]

    def test_no_args(self) -> None:
        @retry()
        def f() -> None:
            pass

        f()

    def test_exception_single_value(self) -> None:
        @retry(ValueError)
        def f() -> None:
            pass

        f()

    def test_exception_sequence(self) -> None:
        @retry((ValueError, TypeError))
        def f() -> None:
            pass

        f()

    def test_exception_type_error(self) -> None:
        with self.assertRaises(TypeError):

            @retry(1)  # type: ignore[arg-type]
            def _() -> None:
                pass

        with self.assertRaises(TypeError):

            @retry((ValueError, 1))  # type: ignore[arg-type]
            def _() -> None:
                pass

    def test_exception_raised_no_retry(self) -> None:
        self.call_count = 0

        @retry(ValueError)
        def f() -> None:
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 1)

    def test_max_attempts(self) -> None:
        self.call_count = 0

        @retry(ValueError, max_attempts=2)
        def f() -> None:
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 2)

    def test_max_attempts_not_int(self) -> None:
        with self.assertRaises(TypeError):

            @retry(ValueError, max_attempts="a")  # type: ignore[arg-type]
            def f() -> None:
                pass

    def test_wait(self) -> None:
        self.call_count = 0

        @retry(ValueError, max_attempts=2, wait=0.001)
        def f() -> None:
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 2)

    def test_wait_not_float(self) -> None:
        with self.assertRaises(TypeError):

            @retry(ValueError, max_attempts=1, wait="a")  # type: ignore[arg-type]
            def f() -> None:
                pass

    def test_stall(self) -> None:
        self.call_count = 0

        @retry(ValueError, max_attempts=2, stall=0.001)
        def f() -> None:
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 2)

    def test_stall_not_float(self) -> None:
        with self.assertRaises(TypeError):

            @retry(ValueError, max_attempts=1, stall="a")  # type: ignore[arg-type]
            def f() -> None:
                pass


class TestStrtobool(TestCase):
    def test_true_values(self) -> None:
        for s in ("y", "yes", "t", "true", "on", "1"):
            self.assertTrue(strtobool(s), s)

    def test_false_values(self) -> None:
        for s in ("n", "no", "f", "false", "off", "0"):
            self.assertFalse(strtobool(s), s)

    def test_raises_value_error(self) -> None:
        for s in ("", "a", "b", "c"):
            with self.assertRaises(ValueError):
                strtobool(s)

    def test_raises_type_error(self) -> None:
        for x in (None, True, False, 1, 2, 3):
            with self.assertRaises(TypeError):
                strtobool(cast("str", x))


class TestTopics(TestCase):
    def test_get_topic(self) -> None:
        self.assertEqual("eventsourcing.domain:Aggregate", get_topic(Aggregate))

        class MyClass:
            TOPIC = "mytopic"

        self.assertEqual("mytopic", get_topic(MyClass))

    def test_resolve_topic(self) -> None:
        self.assertEqual(Aggregate, resolve_topic("eventsourcing.domain:Aggregate"))

    def test_register_topic_rename_class(self) -> None:
        register_topic("eventsourcing.domain:OldClass", Aggregate)
        self.assertEqual(Aggregate, resolve_topic("eventsourcing.domain:OldClass"))
        self.assertEqual(
            Aggregate.Created, resolve_topic("eventsourcing.domain:OldClass.Created")
        )

    def test_register_topic_move_module_into_package(self) -> None:
        register_topic("oldmodule", eventsourcing.domain)
        self.assertEqual(Aggregate, resolve_topic("oldmodule:Aggregate"))
        self.assertEqual(
            Aggregate.Created, resolve_topic("oldmodule:Aggregate.Created")
        )

    def test_register_topic_rename_package(self) -> None:
        register_topic("oldpackage", eventsourcing)
        self.assertEqual(Aggregate, resolve_topic("oldpackage.domain:Aggregate"))
        self.assertEqual(
            Aggregate.Created, resolve_topic("oldpackage.domain:Aggregate.Created")
        )

    def test_register_topic_move_package(self) -> None:
        register_topic("old.eventsourcing.domain", eventsourcing.domain)
        self.assertEqual(Aggregate, resolve_topic("old.eventsourcing.domain:Aggregate"))

    def test_register_topic_rename_package_and_module(self) -> None:
        register_topic("old.old", eventsourcing.domain)
        self.assertEqual(Aggregate, resolve_topic("old.old:Aggregate"))

    def test_topic_errors(self) -> None:
        # Wrong module name.
        with self.assertRaises(TopicError) as cm:
            resolve_topic("oldmodule:Aggregate")
        expected_msg = (
            "Failed to resolve topic 'oldmodule:Aggregate': No module named 'oldmodule'"
        )
        self.assertEqual(expected_msg, cm.exception.args[0])

        # Wrong class name.
        with self.assertRaises(TopicError) as cm:
            resolve_topic("eventsourcing.domain:OldClass")
        expected_msg = (
            "Failed to resolve topic 'eventsourcing.domain:OldClass': "
            "module 'eventsourcing.domain' has no attribute 'OldClass'"
        )
        self.assertEqual(expected_msg, cm.exception.args[0])

        # Wrong class attribute.
        with self.assertRaises(TopicError) as cm:
            resolve_topic("eventsourcing.domain:Aggregate.OldClass")
        expected_msg = (
            "Failed to resolve topic 'eventsourcing.domain:Aggregate.OldClass': "
            "type object 'Aggregate' has no attribute 'OldClass'"
        )
        self.assertEqual(expected_msg, cm.exception.args[0])

        # Can register same thing twice.
        register_topic("old", eventsourcing)
        register_topic("old", eventsourcing)

        # Can't overwrite with another thing.
        with self.assertRaises(TopicError) as cm:
            register_topic("old", TestCase)
        self.assertIn("is already registered for topic 'old'", cm.exception.args[0])

    def tearDown(self) -> None:
        clear_topic_cache()


class TestResolveMultiGenericTargets(TestCase):
    def test_plain_class(self) -> None:
        class A:
            pass

        class B(A):
            pass

        type_args = resolve_multi_generic_target(B, A)
        self.assertEqual(type_args, ())

    def test_sneaky_mro(self) -> None:
        class Base(Generic[_T]):
            pass

        class SneakyBase:
            """A class injected into the MRO, but not inherited from directly."""

        class CustomMROMeta(type):
            def mro(cls) -> list[type]:
                # Standard Python behavior would just return type.mro(cls)
                # We manually inject SneakyBase right before `object`
                return [cls, SneakyBase, object]

        class Sneaky(Base[int], metaclass=CustomMROMeta):
            pass

        type_args = resolve_multi_generic_target(Sneaky, Base)
        self.assertEqual(type_args, (int,))


_T = TypeVar("_T")
