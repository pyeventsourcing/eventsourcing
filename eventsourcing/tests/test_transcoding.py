import datetime
from unittest import TestCase
from uuid import NAMESPACE_URL

from decimal import Decimal

from eventsourcing.domain.model.events import QualnameABC
from eventsourcing.infrastructure.transcoding import ObjectJSONEncoder, ObjectJSONDecoder
from eventsourcing.utils.time import utc_timezone


class TestObjectJSONEncoder(TestCase):
    def test_encode(self):
        encoder = ObjectJSONEncoder()
        expect = '1'
        self.assertEqual(encoder.encode(1), expect)

        value = datetime.datetime(2011, 1, 1, 1, 1, 1)
        expect = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000"}'
        self.assertEqual(encoder.encode(value), expect)

        value = datetime.datetime(2011, 1, 1, 1, 1, 1, tzinfo=utc_timezone)
        expect = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000+0000"}'
        self.assertEqual(encoder.encode(value), expect)

        value = datetime.date(2011, 1, 1)
        expect = '{"ISO8601_date": "2011-01-01"}'
        self.assertEqual(encoder.encode(value), expect)

        value = NAMESPACE_URL
        expect = '{"UUID": "6ba7b8119dad11d180b400c04fd430c8"}'
        self.assertEqual(encoder.encode(value), expect)

        value = Object(NAMESPACE_URL)
        expect = ('{"__class__": {"topic": "eventsourcing.tests.test_transcoding#Object", "state": {"a": {"UUID": '
                  '"6ba7b8119dad11d180b400c04fd430c8"}}}}')
        self.assertEqual(encoder.encode(value), expect)

        # Check defers to base class to raise TypeError.
        # - a Decimal isn't supported at the moment, hence this test works
        # - but maybe it should, in which case we need a different unsupported type here
        with self.assertRaises(TypeError):
            encoder.encode(Decimal(1.0))


class TestObjectJSONDecoder(TestCase):
    def test_decode(self):
        decoder = ObjectJSONDecoder()
        self.assertEqual(decoder.decode('1'), 1)

        value = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000"}'
        expect = datetime.datetime(2011, 1, 1, 1, 1, 1)
        self.assertEqual(decoder.decode(value), expect)

        value = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000+0000"}'
        expect = datetime.datetime(2011, 1, 1, 1, 1, 1, tzinfo=utc_timezone)
        self.assertEqual(decoder.decode(value), expect)

        value = '{"ISO8601_date": "2011-01-01"}'
        expect = datetime.date(2011, 1, 1)
        self.assertEqual(decoder.decode(value), expect)

        value = '{"UUID": "6ba7b8119dad11d180b400c04fd430c8"}'
        expect = NAMESPACE_URL
        self.assertEqual(decoder.decode(value), expect)

        value = ('{"__class__": {"topic": "eventsourcing.tests.test_transcoding#Object", "state": {"a": {"UUID": '
                 '"6ba7b8119dad11d180b400c04fd430c8"}}}}')
        expect = Object(NAMESPACE_URL)
        self.assertEqual(decoder.decode(value), expect)


class Object(QualnameABC):
    def __init__(self, a):
        self.a = a

    def __eq__(self, other):
        return self.a == other.a

