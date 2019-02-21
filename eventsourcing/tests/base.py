import os
import unittest
from abc import ABC
from functools import wraps
from unittest import TestCase


class AbstractTestCase(ABC, TestCase):
    """Base class for abstract test cases.

    Skips tests in all subclass test cases,
    if class name ends with 'TestCase'.
    """

    def setUp(self):
        """Returns None if test case class ends with 'TestCase',
        which means the test case isn't included in the suite.
        """
        super(AbstractTestCase, self).setUp()
        if type(self).__name__.endswith('TestCase'):
            self.skipTest('Ignored abstract test.')
        else:
            super(AbstractTestCase, self).setUp()


def notquick(arg):
    @wraps(arg)
    def _not_quick(arg):
        return unittest.skipIf(os.getenv("QUICK_TESTS_ONLY"), 'Ignored slow test.')(arg)

    return _not_quick(arg)
