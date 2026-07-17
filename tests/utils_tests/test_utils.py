from typing import Generic, cast
from unittest import TestCase

from typing_extensions import TypeVar

import eventsourcing
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
                strtobool(cast(str, x))


class Outer:
    class Inner:
        pass


class OuterWithTopic:
    TOPIC = "outertopic"

    class InnerWithTopic:
        TOPIC = "innertopic"


class TestTopics(TestCase):
    def setUp(self) -> None:
        clear_topic_cache()

    def tearDown(self) -> None:
        clear_topic_cache()

    def test_get_topic(self) -> None:
        self.assertEqual(
            "tests.utils_tests.test_utils:Outer",
            get_topic(Outer),
        )
        self.assertEqual(
            "tests.utils_tests.test_utils:Outer.Inner",
            get_topic(Outer.Inner),
        )

        self.assertEqual("outertopic", get_topic(OuterWithTopic))
        self.assertEqual("innertopic", get_topic(OuterWithTopic.InnerWithTopic))

    def test_resolve_topic(self) -> None:
        self.assertEqual(Outer, resolve_topic("tests.utils_tests.test_utils:Outer"))

    def test_register_topic_rename_class(self) -> None:
        old_topic = "tests.utils_tests.test_utils:OldClass"
        register_topic(old_topic, Outer)
        self.assertEqual(Outer, resolve_topic(old_topic))
        self.assertEqual(
            Outer.Inner,
            resolve_topic(old_topic + ".Inner"),
        )

    def test_register_topic_move_module_into_package(self) -> None:
        this = resolve_topic(Outer.__module__)
        clear_topic_cache()
        old_topic = "oldmodule"
        register_topic(old_topic, this)
        self.assertEqual(Outer, resolve_topic("oldmodule:Outer"))
        self.assertEqual(Outer.Inner, resolve_topic("oldmodule:Outer.Inner"))

    def test_register_topic_rename_package(self) -> None:
        tests = resolve_topic("tests")
        clear_topic_cache()
        register_topic("oldpackage", tests)
        self.assertEqual(
            Outer, resolve_topic("oldpackage.utils_tests.test_utils:Outer")
        )
        self.assertEqual(
            Outer.Inner, resolve_topic("oldpackage.utils_tests.test_utils:Outer.Inner")
        )

    def test_register_topic_move_package(self) -> None:
        this = resolve_topic(Outer.__module__)
        clear_topic_cache()
        old_topic = "old." + Outer.__module__
        register_topic(old_topic, this)
        self.assertEqual(Outer, resolve_topic(f"{old_topic}:Outer"))

    def test_register_topic_rename_package_and_module(self) -> None:
        this = resolve_topic(Outer.__module__)
        clear_topic_cache()
        register_topic("old.old", this)
        self.assertEqual(Outer, resolve_topic("old.old:Outer"))

    def test_topic_errors(self) -> None:
        # Wrong module name.
        with self.assertRaises(TopicError) as cm:
            resolve_topic("oldmodule:Outer")
        expected_msg = (
            "Failed to resolve topic 'oldmodule:Outer': No module named 'oldmodule'"
        )
        self.assertEqual(expected_msg, cm.exception.args[0])

        # Wrong class name.
        with self.assertRaises(TopicError) as cm:
            resolve_topic(f"{Outer.__module__}:OldClass")
        expected_msg = (
            f"Failed to resolve topic '{Outer.__module__}:OldClass': "
            f"module '{Outer.__module__}' has no attribute 'OldClass'"
        )
        self.assertEqual(expected_msg, cm.exception.args[0])

        # Wrong class attribute.
        with self.assertRaises(TopicError) as cm:
            resolve_topic(f"{Outer.__module__}:Outer.OldClass")
        expected_msg = (
            f"Failed to resolve topic '{Outer.__module__}:Outer.OldClass': "
            "type object 'Outer' has no attribute 'OldClass'"
        )
        self.assertEqual(expected_msg, cm.exception.args[0])

        # Can register same thing twice.
        register_topic("old", eventsourcing)
        register_topic("old", eventsourcing)

        # Can't overwrite with another thing.
        with self.assertRaises(TopicError) as cm:
            register_topic("old", TestCase)
        self.assertIn("is already registered for topic 'old'", cm.exception.args[0])


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
