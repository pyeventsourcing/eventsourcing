import datetime
from collections import deque, namedtuple
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from unittest import TestCase, skipIf
from uuid import NAMESPACE_URL, UUID

from eventsourcing.utils.times import utc_timezone
from eventsourcing.utils.transcoding_v1 import ObjectJSONDecoder, ObjectJSONEncoder

try:
    from dataclasses import make_dataclass
except:
    make_dataclass = None


class TestTranscoding(TestCase):
    def test_str(self):
        value = "a string"
        encoded = '"a string"'
        self.assertTranscoding(value, encoded)

    def test_str_type(self):
        value = str
        encoded = '{"__type__": "builtins#str"}'
        self.assertTranscoding(value, encoded)

    def test_int(self):
        value = 1
        encoded = "1"
        self.assertTranscoding(value, encoded)

    def test_int_type(self):
        value = int
        encoded = '{"__type__": "builtins#int"}'
        self.assertTranscoding(value, encoded)

    def test_float(self):
        value = 1.001
        encoded = "1.001"
        self.assertTranscoding(value, encoded)

    def test_float_type(self):
        value = float
        encoded = '{"__type__": "builtins#float"}'
        self.assertTranscoding(value, encoded)

    def test_datetime_without_tzinfo(self):
        value = datetime.datetime(2011, 1, 1, 1, 1, 1)
        encoded = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000"}'
        self.assertTranscoding(value, encoded)

    def test_datetime_with_tzinfo(self):
        value = datetime.datetime(2011, 1, 1, 1, 1, 1, tzinfo=utc_timezone)
        encoded = '{"ISO8601_datetime": "2011-01-01T01:01:01.000000+0000"}'
        self.assertTranscoding(value, encoded)

    def test_datetime_type(self):
        value = datetime.datetime
        encoded = '{"__type__": "datetime#datetime"}'
        self.assertTranscoding(value, encoded)

    def test_date(self):
        value = datetime.date(2011, 1, 1)
        encoded = '{"ISO8601_date": "2011-01-01"}'
        self.assertTranscoding(value, encoded)

    def test_date_type(self):
        value = datetime.date
        encoded = '{"__type__": "datetime#date"}'
        self.assertTranscoding(value, encoded)

    def test_time(self):
        value = datetime.time(23, 59, 59, 123456)
        encoded = '{"ISO8601_time": "23:59:59.123456"}'
        self.assertTranscoding(value, encoded)

    def test_time_type(self):
        value = datetime.time
        encoded = '{"__type__": "datetime#time"}'
        self.assertTranscoding(value, encoded)

    def test_decimal(self):
        value = Decimal("59.123456")
        encoded = '{"__decimal__": "59.123456"}'
        self.assertTranscoding(value, encoded)

    def test_decimal_type(self):
        value = Decimal
        encoded = '{"__type__": "decimal#Decimal"}'
        self.assertTranscoding(value, encoded)

    def test_fraction(self):
        value = Fraction(1, 3)
        encoded = (
            '{"__class__": {"state": {"_denominator": 3, "_numerator": 1}, '
            '"topic": "fractions#Fraction"}}'
        )
        self.assertTranscoding(value, encoded)

    def test_fraction_type(self):
        value = Fraction
        encoded = '{"__type__": "fractions#Fraction"}'
        self.assertTranscoding(value, encoded)

    def test_enum(self):
        value = Colour.GREEN
        encoded = (
            '{"__enum__": {"name": "GREEN", "topic": '
            '"eventsourcing.tests.test_transcoding_v1#Colour"}}'
        )
        self.assertTranscoding(value, encoded)

    def test_uuid(self):
        value = NAMESPACE_URL
        encoded = '{"UUID": "6ba7b8119dad11d180b400c04fd430c8"}'
        self.assertTranscoding(value, encoded)

    def test_uuid_type(self):
        value = UUID
        encoded = '{"__type__": "uuid#UUID"}'
        self.assertTranscoding(value, encoded)

    def test_tuple(self):
        value = (1, 2, 4)
        encoded = '{"__tuple__": {"state": [1, 2, 4], "topic": "builtins#tuple"}}'
        self.assertTranscoding(value, encoded)

    def test_tuple_type(self):
        value = tuple
        encoded = '{"__type__": "builtins#tuple"}'
        self.assertTranscoding(value, encoded)

    def test_list(self):
        value = [1, 2, 4]
        encoded = "[1, 2, 4]"
        self.assertTranscoding(value, encoded)

    def test_list_type(self):
        value = list
        encoded = '{"__type__": "builtins#list"}'
        self.assertTranscoding(value, encoded)

    def test_set(self):
        value = {1, 2, 4}
        encoded = '{"__set__": [1, 2, 4]}'
        self.assertTranscoding(value, encoded)

    def test_set_type(self):
        value = set
        encoded = '{"__type__": "builtins#set"}'
        self.assertTranscoding(value, encoded)

    def test_namedtuple(self):
        value = MyNamedTuple(a=1, b="2", c=MyObjectClass([3, "4"]))
        encoded = (
            '{"__tuple__": {"state": [1, "2", {"__class__": {"state": '
            '{"a": [3, "4"]}, "topic": "eventsourcing.tests.test_trans'
            'coding_v1#MyObjectClass"}}], "topic": "eventsourcing.tests.t'
            'est_transcoding_v1#MyNamedTuple"}}'
        )
        self.assertTranscoding(value, encoded)

    def test_namedtuple_type(self):
        value = MyNamedTuple
        encoded = '{"__type__": "eventsourcing.tests.test_transcoding_v1#MyNamedTuple"}'
        self.assertTranscoding(value, encoded)

    def test_object_with_dict(self):
        self.assertEqual(MyObjectClass(NAMESPACE_URL), MyObjectClass(NAMESPACE_URL))
        value = MyObjectClass(NAMESPACE_URL)
        encoded = (
            '{"__class__": {"state": {"a": {"UUID": "6ba7b8119dad11d18'
            '0b400c04fd430c8"}}, "topic": "eventsourcing.tests.test_tr'
            'anscoding_v1#MyObjectClass"}}'
        )
        self.assertTranscoding(value, encoded)

    def test_object_with_dict_type(self):
        value = MyObjectClass
        encoded = (
            '{"__type__": "eventsourcing.tests.test_transcoding_v1#MyObjectClass"}'
        )
        self.assertTranscoding(value, encoded)

    def test_object_with_slots(self):
        instance1 = MySlottedClass(a=1, b=2, c=3)
        instance2 = MySlottedClass(a=2, b=2, c=3)
        self.assertEqual(instance1, instance1)
        self.assertNotEqual(instance2, instance1)
        value = instance1
        encoded = (
            '{"__class__": {"state": {"a": 1, "b": 2, "c": 3}, "topic":'
            ' "eventsourcing.tests.test_transcoding_v1#MySlottedClass"}}'
        )
        self.assertTranscoding(value, encoded)

    def test_object_with_slots_type(self):
        value = MySlottedClass
        encoded = (
            '{"__type__": "eventsourcing.tests.test_transcoding_v1#MySlottedClass"}'
        )
        self.assertTranscoding(value, encoded)

    @skipIf(make_dataclass is None, "Dataclasses are not supported")
    def test_dataclass_object(self):
        value = MyDataClass(1, "2", Decimal("3.0"))
        encoded = (
            '{"__class__": {"state": {"a": 1, "b": "2", "c": {'
            '"__decimal__": "3.0"}}, "topic": "eventsourcing.t'
            'ests.test_transcoding_v1#MyDataClass"}}'
        )
        self.assertTranscoding(value, encoded)

    @skipIf(make_dataclass is None, "Dataclasses are not supported")
    def test_dataclass_object_type(self):
        value = MyDataClass
        encoded = '{"__type__": "eventsourcing.tests.test_transcoding_v1#MyDataClass"}'
        self.assertTranscoding(value, encoded)

    def test_deque(self):
        value = deque([1, 3, 2])
        encoded = '{"__deque__": {"topic": "collections#deque", "values": [1, 3, 2]}}'
        self.assertTranscoding(value, encoded)

        value = MyDeque([1, 3, 2])
        encoded = (
            '{"__deque__": {"topic": "eventsourcing.tests.test_transcoding_v1#MyDeque", '
            '"values": [1, 3, 2]}}'
        )
        self.assertTranscoding(value, encoded)

    def test_bytes(self):
        value = b"abc"
        encoded = '{"__bytes__": "YWJj"}'
        self.assertTranscoding(value, encoded)

    def test_encode_exception_method(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works
        with self.assertRaises(TypeError):
            self.encode(self.test_encode_exception_method)

    def test_encode_exception_function(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works

        def my_function():
            pass

        with self.assertRaises(TypeError):
            print(self.encode(my_function))

    def test_encode_exception_lambda(self):
        # Check defers to base class to raise TypeError.
        # - a lambda function isn't supported at the moment, hence this test works

        with self.assertRaises(TypeError):
            self.encode(lambda: 1)

    def test_encode_exception_range(self):
        # Check defers to base class to raise TypeError.
        # - a type isn't supported at the moment, hence this test works

        with self.assertRaises(TypeError):
            self.encode(range(10))

    def test_decode_exception_invalid_json(self):
        # Check raises ValueError when JSON string is invalid.
        with self.assertRaises(ValueError):
            self.decode("{")

    def test_json_loads_exception(self):
        # Check raises ValueError when JSON string is invalid.
        with self.assertRaises(ValueError):
            self.decode("{")

    def assertTranscoding(self, value, encoded):
        self.assertEqual(encoded, self.encode(value).decode("utf8"))
        self.assertEqual(value, self.decode(encoded))

    def decode(self, encoded):
        return self.decoder.decode(encoded)

    def encode(self, value):
        return self.encoder.encode(value)

    def setUp(self):
        self.encoder = ObjectJSONEncoder(sort_keys=True)
        self.decoder = ObjectJSONDecoder()


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


if make_dataclass:
    # This decorator-style syntax with typed class attributes
    # prevents the module from loading in pypy3.5:
    #
    # @dataclass
    # class MyDataClass:
    #     a: int
    #     b: str
    #     c: Decimal
    #
    # So I needed to do this instead:
    #
    MyDataClass = make_dataclass("MyDataClass", ["a", "b", "c"])
    MyDataClass.__module__ = __name__


class Colour(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


class MyDeque(deque):
    pass
