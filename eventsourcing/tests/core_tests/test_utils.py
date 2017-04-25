import time
from datetime import datetime, timedelta
from unittest.case import TestCase
from uuid import uuid1

import sys

from eventsourcing.utils.time import timestamp_from_uuid, utc_timezone


class TestUtils(TestCase):
    def test_timestamp_from_uuid(self):
        until = time.time()
        uuid = uuid1()
        after = time.time()
        uuid_timestamp = timestamp_from_uuid(uuid)
        self.assertLess(until, uuid_timestamp)
        self.assertGreater(after, uuid_timestamp)

        # Check timestamp_from_uuid() works with hex strings, as well as UUID objects.
        self.assertEqual(timestamp_from_uuid(uuid.hex), timestamp_from_uuid(uuid))

    def test_utc(self):
        now = datetime.now(tz=utc_timezone)
        self.assertEqual(utc_timezone.utcoffset(now), timedelta(0))
        expected_dst = None if int(sys.version[0]) > 2 else timedelta(0)
        self.assertEqual(utc_timezone.dst(now), expected_dst)
