import os
from datetime import datetime, timedelta
from decimal import Decimal
from time import sleep
from unittest.case import TestCase
from uuid import uuid1

import sys

from eventsourcing.utils.random import encode_random_bytes, decode_bytes
from eventsourcing.utils.times import decimaltimestamp_from_uuid, utc_timezone, decimaltimestamp


class TestUtils(TestCase):
    def test_decimaltimestamp(self):
        # Check a given float is correctly converted to a Decimal.
        self.assertEqual(decimaltimestamp(123456789.1234560), Decimal('123456789.123456'))
        self.assertEqual(decimaltimestamp(1234567890.1234560), Decimal('1234567890.123456'))

        # Generate a series of timestamps.
        timestamps = [decimaltimestamp() for _ in range(100)]

        # Check series doesn't decrease at any point.
        last = timestamps[0]
        for timestamp in timestamps[1:]:
            self.assertLessEqual(last, timestamp)
            last = timestamp

        # Check last timestamp is greater than the first.
        self.assertGreater(timestamps[-1], timestamps[0])

    def test_decimaltimestamp_from_uuid(self):
        # Check can convert a UUID to a Decimal.
        self.assertIsInstance(decimaltimestamp_from_uuid(uuid1()), Decimal)
        # Check can convert a UUID hex to a Decimal.
        self.assertIsInstance(decimaltimestamp_from_uuid(uuid1().hex), Decimal)

        # Generate a series of timestamps.
        timestamps = [decimaltimestamp_from_uuid(uuid1()) for _ in range(100)]

        # Check series doesn't decrease at any point.
        last = timestamps[0]
        for timestamp in timestamps[1:]:
            self.assertLessEqual(last, timestamp)
            last = timestamp

        # Check last timestamp is greater than the first.
        self.assertGreater(timestamps[-1], timestamps[0])

    def test_decimaltimestamp_corresponds_with_decimaltimestamp_from_uuid(self):
        if os.getenv('TRAVIS_PYTHON_VERSION') in ['3.6', '3.7', '3.7-dev', 'pypy3.5']:
            self.skipTest("Somehow this fails on Travis dist:xenial.")

            # This is the weird error that happens in Python 3.7.1 on Travis Xenial dist.
            # Why does the second timestamp "happen" more than one second before the first?
            # Perhaps UUID1 doesn't actually use time.time() sometimes? Maybe it was a bug in v3.7.1?
            """
FAIL: test_decimaltimestamp_corresponds_with_decimaltimestamp_from_uuid (
eventsourcing.tests.core_tests.test_utils.TestUtils)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/travis/build/johnbywater/eventsourcing/eventsourcing/tests/core_tests/test_utils.py", line 61,
  in test_decimaltimestamp_corresponds_with_decimaltimestamp_from_uuid
    self.assertLess(timestamp1, timestamp2)
AssertionError: Decimal('1561464862.322443') not less than Decimal('1561464861.100940')
            """

        timestamp1 = decimaltimestamp()
        sleep(0.000001)
        uuid_1 = uuid1()
        sleep(0.000001)
        timestamp3 = decimaltimestamp()
        sleep(0.000001)
        timestamp2 = decimaltimestamp_from_uuid(uuid_1)
        self.assertLess(timestamp1, timestamp2)
        self.assertLess(timestamp2, timestamp3)

    def test_utc(self):
        now = datetime.now(tz=utc_timezone)
        self.assertEqual(utc_timezone.utcoffset(now), timedelta(0))
        expected_dst = None if int(sys.version[0]) > 2 else timedelta(0)
        self.assertEqual(utc_timezone.dst(now), expected_dst)

    def test_encode_random_bytes(self):
        key = encode_random_bytes(num_bytes=16)
        self.assertEqual(len(decode_bytes(key)), 16)

        key = encode_random_bytes(num_bytes=24)
        self.assertEqual(len(decode_bytes(key)), 24)

        key = encode_random_bytes(num_bytes=32)
        self.assertEqual(len(decode_bytes(key)), 32)
