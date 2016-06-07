from unittest.case import TestCase
from uuid import uuid1

from eventsourcing.utils.time import utc_now, timestamp_from_uuid


class TestUtils(TestCase):

    def test_timestamp_from_uuid(self):
        until = utc_now()
        uuid = uuid1()
        after = utc_now()
        uuid_timestamp = timestamp_from_uuid(uuid)
        self.assertLess(until, uuid_timestamp)
        self.assertGreater(after, uuid_timestamp)
