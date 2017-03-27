import os
import unittest
from unittest import TestCase


class AbstractTestCase(TestCase):
    """
    Base class for test cases with abstract test_* methods.
    """

    def setUp(self):
        """
        Returns None if test case class ends with 'TestCase',
        which means the test case isn't included in the suite.
        """
        super(AbstractTestCase, self).setUp()
        if type(self).__name__.endswith('TestCase'):
            self.skipTest('Ignored abstract test.')
        else:
            super(AbstractTestCase, self).setUp()


def notquick(*args, **kwargs):
    return unittest.skipIf(os.getenv("QUICK_TESTS_ONLY"), 'Ignored slow test.')
