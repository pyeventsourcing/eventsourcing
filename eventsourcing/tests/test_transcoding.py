import datetime
from collections import deque, namedtuple

import sys

if sys.version_info >= (3, 7):
    from dataclasses import make_dataclass

from decimal import Decimal
from unittest import TestCase
from uuid import NAMESPACE_URL, UUID

from eventsourcing.utils.times import utc_timezone
from eventsourcing.utils.transcoding import (
    ObjectJSONDecoder,
    ObjectJSONEncoder,
    json_loads,
    json_dumps)


class TestTranscoding(TestCase):
    def test_str(self):
        value = "a string"
        encoded = '"a string"'
        self.assertIsTranscoded(value, encoded)

    def test_str_type(self):
        value = str
        encoded = '{"__type__": "builtins#str"}'
        self.assertIsTranscoded(value, encoded)

    def test_int(self):
        value = 1
        encoded = "1"
        self.assertIsTranscoded(value, encoded)

    def test_int_type(self):
        value = int
        encoded = '{"__type__": "builtins#int"}'
        self.assertIsTranscoded(value, encoded)

    def test_float(self):
        value = 1.001
        encoded = "1.001"
        self.assertIsTranscoded(value, encoded)

    def test_float_type(self):
        value = float
        encoded = '{"__type__": "builtins#float"}'
        self.assertIsTranscoded(value, encoded)

    def test_datetime_without_tzinfo(self):
        value = datetime.datetime(2011, 1, 1, 1, 1, 1)
        encoded = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000"}'
        self.assertIsTranscoded(value, encoded)

    def test_datetime_with_tzinfo(self):
        value = datetime.datetime(2011, 1, 1, 1, 1, 1, tzinfo=utc_timezone)
        encoded = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000+0000"}'
        self.assertIsTranscoded(value, encoded)

    def test_datetime_type(self):
        value = datetime.datetime
        encoded = '{"__type__": "datetime#datetime"}'
        self.assertIsTranscoded(value, encoded)

    def test_date(self):
        value = datetime.date(2011, 1, 1)
        encoded = '{"ISO8601_date": "2011-01-01"}'
        self.assertIsTranscoded(value, encoded)

    def test_date_type(self):
        value = datetime.date
        encoded = '{"__type__": "datetime#date"}'
        self.assertIsTranscoded(value, encoded)

    def test_time(self):
        value = datetime.time(23, 59, 59, 123456)
        encoded = '{"ISO8601_time": "23:59:59.123456"}'
        self.assertIsTranscoded(value, encoded)

    def test_time_type(self):
        value = datetime.time
        encoded = '{"__type__": "datetime#time"}'
        self.assertIsTranscoded(value, encoded)

    def test_decimal(self):
        value = Decimal("59.123456")
        encoded = '{"__decimal__": "59.123456"}'
        self.assertIsTranscoded(value, encoded)

    def test_decimal_type(self):
        value = Decimal
        encoded = '{"__type__": "decimal#Decimal"}'
        self.assertIsTranscoded(value, encoded)

    def test_uuid(self):
        value = NAMESPACE_URL
        encoded = '{"UUID": "6ba7b8119dad11d180b400c04fd430c8"}'
        self.assertIsTranscoded(value, encoded)

    def test_uuid_type(self):
        value = UUID
        encoded = '{"__type__": "uuid#UUID"}'
        self.assertIsTranscoded(value, encoded)

    def test_tuple(self):
        value = (1, 2, 4)
        encoded = '{"__tuple__": {"state": [1, 2, 4], "topic": "builtins#tuple"}}'
        self.assertIsTranscoded(value, encoded)

    def test_tuple_type(self):
        value = tuple
        encoded = '{"__type__": "builtins#tuple"}'
        self.assertIsTranscoded(value, encoded)

    def test_list(self):
        value = [1, 2, 4]
        encoded = "[1, 2, 4]"
        self.assertIsTranscoded(value, encoded)

    def test_list_type(self):
        value = list
        encoded = '{"__type__": "builtins#list"}'
        self.assertIsTranscoded(value, encoded)

    def test_set(self):
        value = {1, 2, 4}
        encoded = '{"__set__": [1, 2, 4]}'
        self.assertIsTranscoded(value, encoded)

    def test_set_type(self):
        value = set
        encoded = '{"__type__": "builtins#set"}'
        self.assertIsTranscoded(value, encoded)

    def test_namedtuple(self):
        value = MyNamedTuple(a=1, b="2", c=MyObjectClass([3, "4"]))
        encoded = (
            '{"__tuple__": {"state": [1, "2", {"__class__": {"state": '
            '{"a": [3, "4"]}, "topic": "eventsourcing.tests.test_trans'
            'coding#MyObjectClass"}}], "topic": "eventsourcing.tests.t'
            'est_transcoding#MyNamedTuple"}}'
        )
        self.assertIsTranscoded(value, encoded)

    def test_namedtuple_type(self):
        value = MyNamedTuple
        encoded = '{"__type__": "eventsourcing.tests.test_transcoding#MyNamedTuple"}'
        self.assertIsTranscoded(value, encoded)

    def test_object_with_dict(self):
        self.assertEqual(MyObjectClass(NAMESPACE_URL), MyObjectClass(NAMESPACE_URL))
        value = MyObjectClass(NAMESPACE_URL)
        encoded = (
            '{"__class__": {"state": {"a": {"UUID": "6ba7b8119dad11d18'
            '0b400c04fd430c8"}}, "topic": "eventsourcing.tests.test_tr'
            'anscoding#MyObjectClass"}}'
        )
        self.assertIsTranscoded(value, encoded)

    def test_object_with_dict_type(self):
        value = MyObjectClass
        encoded = '{"__type__": "eventsourcing.tests.test_transcoding#MyObjectClass"}'
        self.assertIsTranscoded(value, encoded)

    def test_object_with_slots(self):
        instance1 = MySlottedClass(a=1, b=2, c=3)
        instance2 = MySlottedClass(a=2, b=2, c=3)
        self.assertEqual(instance1, instance1)
        self.assertNotEqual(instance2, instance1)
        value = instance1
        encoded = (
            '{"__class__": {"state": {"a": 1, "b": 2, "c": 3}, "topic":'
            ' "eventsourcing.tests.test_transcoding#MySlottedClass"}}'
        )
        self.assertIsTranscoded(value, encoded)

    def test_object_with_slots_type(self):
        value = MySlottedClass
        encoded = '{"__type__": "eventsourcing.tests.test_transcoding#MySlottedClass"}'
        self.assertIsTranscoded(value, encoded)

    def test_dataclass_object(self):
        if sys.version_info >= (3, 7):
            value = MyDataClass(1, "2", Decimal("3.0"))
            encoded = (
                '{"__class__": {"state": {"a": 1, "b": "2", "c": {'
                '"__decimal__": "3.0"}}, "topic": "eventsourcing.t'
                'ests.test_transcoding#MyDataClass"}}'
            )
            self.assertIsTranscoded(value, encoded)

    def test_dataclass_object_type(self):
        value = MyDataClass
        encoded = '{"__type__": "eventsourcing.tests.test_transcoding#MyDataClass"}'
        self.assertIsTranscoded(value, encoded)

    def test_deque_empty(self):
        value = deque()
        encoded = '{"__deque__": []}'
        self.assertIsTranscoded(value, encoded)

    def test_encode_exception_non_empty_deque(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works
        with self.assertRaises(ValueError):
            self.json_dumps(deque([1]))

    def test_encode_exception_method(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works
        with self.assertRaises(TypeError):
            self.json_dumps(self.test_encode_exception_method)

    def test_encode_exception_function(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works

        def my_function():
            pass

        with self.assertRaises(TypeError):
            print(self.json_dumps(my_function))

    def test_encode_exception_lambda(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works

        with self.assertRaises(TypeError):
            self.json_dumps(lambda: 1)

    def test_encode_exception_range(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works

        with self.assertRaises(TypeError):
            self.json_dumps(range(10))

    def test_decode_exception_invalid_json(self):
        # Check raises ValueError when JSON string is invalid.
        with self.assertRaises(ValueError):
            self.json_loads("{")

    def test_json_loads_exception(self):
        # Check raises ValueError when JSON string is invalid.
        with self.assertRaises(ValueError):
            self.json_loads("{")

    def assertIsTranscoded(self, value, encoded):
        self.assertEqual(encoded, self.json_dumps(value))
        self.assertEqual(value, self.json_loads(encoded))

    def json_loads(self, encoded):
        return json_loads(encoded, ObjectJSONDecoder)

    def json_dumps(self, value):
        return json_dumps(value, ObjectJSONEncoder)


class MyObjectClass:
    def __init__(self, a):
        self.a = a

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


MyNamedTuple = namedtuple("MyNamedTuple", field_names=["a", "b", "c"])


class MySlottedClass:
    __slots__ = ["a", "b", "c"]

    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    def __eq__(self, other):
        return all(getattr(self, a) == getattr(other, a) for a in self.__slots__)


if sys.version_info >= (3, 7):
    # This prevents the module loading in pypy3.5:
    #
    # @dataclass
    # class MyDataClass:
    #     a: int
    #     b: str
    #     c: Decimal
    #
    # So need to do this instead:
    #
    MyDataClass = make_dataclass("MyDataClass", ["a", "b", "c"])
    MyDataClass.__module__ = __name__
