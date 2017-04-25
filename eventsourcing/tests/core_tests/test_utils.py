import datetime
from unittest.case import TestCase
from uuid import uuid1

from eventsourcing.utils.time import timestamp_from_uuid, utc_timezone


class TestUtils(TestCase):
    def test_timestamp_from_uuid(self):
        until = utc_now()
        uuid = uuid1()
        after = utc_now()
        uuid_timestamp = timestamp_from_uuid(uuid)
        self.assertLess(until, uuid_timestamp)
        self.assertGreater(after, uuid_timestamp)

        # Check it works with hex strings, as well as UUID objects.
        self.assertEqual(timestamp_from_uuid(uuid.hex), timestamp_from_uuid(uuid))


def utc_now():
    now_datetime = datetime.datetime.now(utc_timezone)
    try:
        now_timestamp = now_datetime.timestamp()
    except AttributeError:
        now_timestamp = (now_datetime - datetime.datetime(1970, 1, 1, tzinfo=utc_timezone)).total_seconds()
    return now_timestamp
