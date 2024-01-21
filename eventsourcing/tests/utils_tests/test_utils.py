from typing import cast
from unittest import TestCase

import eventsourcing
from eventsourcing.domain import Aggregate
from eventsourcing.utils import (
    TopicError,
    clear_topic_cache,
    get_topic,
    register_topic,
    resolve_topic,
    retry,
    strtobool,
)


class TestRetryDecorator(TestCase):
    def test_bare(self):
        @retry
        def f():
            pass

        f()

    def test_no_args(self):
        @retry()
        def f():
            pass

        f()

    def test_exception_single_value(self):
        @retry(ValueError)
        def f():
            pass

        f()

    def test_exception_sequence(self):
        @retry((ValueError, TypeError))
        def f():
            pass

        f()

    def test_exception_type_error(self):
        with self.assertRaises(TypeError):

            @retry(1)
            def _():
                pass

        with self.assertRaises(TypeError):

            @retry((ValueError, 1))
            def _():
                pass

    def test_exception_raised_no_retry(self):
        self.call_count = 0

        @retry(ValueError)
        def f():
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 1)

    def test_max_attempts(self):
        self.call_count = 0

        @retry(ValueError, max_attempts=2)
        def f():
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 2)

    def test_max_attempts_not_int(self):
        with self.assertRaises(TypeError):

            @retry(ValueError, max_attempts="a")
            def f():
                pass

    def test_wait(self):
        self.call_count = 0

        @retry(ValueError, max_attempts=2, wait=0.001)
        def f():
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 2)

    def test_wait_not_float(self):
        with self.assertRaises(TypeError):

            @retry(ValueError, max_attempts=1, wait="a")
            def f():
                pass

    def test_stall(self):
        self.call_count = 0

        @retry(ValueError, max_attempts=2, stall=0.001)
        def f():
            self.call_count += 1
            raise ValueError

        with self.assertRaises(ValueError):
            f()

        self.assertEqual(self.call_count, 2)

    def test_stall_not_float(self):
        with self.assertRaises(TypeError):

            @retry(ValueError, max_attempts=1, stall="a")
            def f():
                pass


class TestStrtobool(TestCase):
    def test_true_values(self):
        for s in ("y", "yes", "t", "true", "on", "1"):
            self.assertTrue(strtobool(s), s)

    def test_false_values(self):
        for s in ("n", "no", "f", "false", "off", "0"):
            self.assertFalse(strtobool(s), s)

    def test_raises_value_error(self):
        for s in ("", "a", "b", "c"):
            with self.assertRaises(ValueError):
                strtobool(s)

    def test_raises_type_error(self):
        for x in (None, True, False, 1, 2, 3):
            with self.assertRaises(TypeError):
                strtobool(cast(str, x))


class TestTopics(TestCase):
    def test_get_topic(self):
        self.assertEqual("eventsourcing.domain:Aggregate", get_topic(Aggregate))

    def test_resolve_topic(self):
        self.assertEqual(Aggregate, resolve_topic("eventsourcing.domain:Aggregate"))

    def test_register_topic_rename_class(self):
        register_topic("eventsourcing.domain:OldClass", Aggregate)
        self.assertEqual(Aggregate, resolve_topic("eventsourcing.domain:OldClass"))
        self.assertEqual(
            Aggregate.Created, resolve_topic("eventsourcing.domain:OldClass.Created")
        )

    def test_register_topic_move_module_into_package(self):
        register_topic("oldmodule", eventsourcing.domain)
        self.assertEqual(Aggregate, resolve_topic("oldmodule:Aggregate"))
        self.assertEqual(
            Aggregate.Created, resolve_topic("oldmodule:Aggregate.Created")
        )

    def test_register_topic_rename_package(self):
        register_topic("oldpackage", eventsourcing)
        self.assertEqual(Aggregate, resolve_topic("oldpackage.domain:Aggregate"))
        self.assertEqual(
            Aggregate.Created, resolve_topic("oldpackage.domain:Aggregate.Created")
        )

    def test_register_topic_move_package(self):
        register_topic("old.eventsourcing.domain", eventsourcing.domain)
        self.assertEqual(Aggregate, resolve_topic("old.eventsourcing.domain:Aggregate"))

    def test_register_topic_rename_package_and_module(self):
        register_topic("old.old", eventsourcing.domain)
        self.assertEqual(Aggregate, resolve_topic("old.old:Aggregate"))

    def test_topic_errors(self):
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
