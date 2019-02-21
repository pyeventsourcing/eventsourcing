import time
from datetime import datetime, timedelta
from unittest.case import TestCase
from uuid import uuid1

import sys

from eventsourcing.utils.random import encode_random_bytes, decode_bytes
from eventsourcing.utils.times import decimaltimestamp_from_uuid, utc_timezone, decimaltimestamp


class TestUtils(TestCase):
    def test_timestamp_from_uuid(self):
        until = decimaltimestamp()
        uuid = uuid1()
        after = decimaltimestamp()
        uuid_timestamp = decimaltimestamp_from_uuid(uuid)
        self.assertLess(until, uuid_timestamp)
        self.assertGreater(after, uuid_timestamp)

        # Check timestamp_from_uuid() works with hex strings, as well as UUID objects.
        self.assertEqual(decimaltimestamp_from_uuid(uuid.hex), decimaltimestamp_from_uuid(uuid))

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
