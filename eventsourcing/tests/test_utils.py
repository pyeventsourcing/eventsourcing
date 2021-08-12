from typing import cast
from unittest import TestCase

from eventsourcing.utils import retry, strtobool


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
