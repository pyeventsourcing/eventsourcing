from unittest import TestCase
from uuid import UUID

from eventsourcing.persistence import Transcoding, JSONTranscoder, UUIDAsHex


class CustomType1:
    def __init__(self, value: UUID):
        self.value = value


class CustomType2:
    def __init__(self, value: CustomType1):
        self.value = value


class CustomType1AsDict(Transcoding):
    type = CustomType1
    name = "custom_type1_as_dict"

    def encode(self, obj: CustomType1) -> UUID:
        return obj.value

    def decode(self, data: UUID) -> CustomType1:
        assert isinstance(data, UUID)
        return CustomType1(value=data)


class CustomType2AsDict(Transcoding):
    type = CustomType2
    name = "custom_type2_as_dict"

    def encode(self, obj: CustomType2) -> CustomType1:
        return obj.value

    def decode(self, data: CustomType1) -> CustomType2:
        assert isinstance(data, CustomType1)
        return CustomType2(data)


class TestJSONTranscoder(TestCase):
    def test_nested_custom_type(self):
        transcoder = JSONTranscoder()
        obj = CustomType2(CustomType1(UUID("b2723fe2c01a40d2875ea3aac6a09ff5")))
        with self.assertRaises(TypeError) as cm:
            transcoder.encode(obj)

        self.assertEqual(
            cm.exception.args[0],
            (
                "Object of type <class 'eventsourcing.tests.persistence_tests."
                "test_eventmapper.CustomType2'> is not serializable. Please define "
                "and register a custom transcoding for this type."
            ),
        )

        transcoder.register(UUIDAsHex())
        transcoder.register(CustomType1AsDict())
        transcoder.register(CustomType2AsDict())

        data = transcoder.encode(obj)
        expect = (
            b'{"_type_": "custom_type2_as_dict", "_data_": '
            b'{"_type_": "custom_type1_as_dict", "_data_": '
            b'{"_type_": "uuid_hex", "_data_": "b2723fe2c01'
            b'a40d2875ea3aac6a09ff5"}}}'
        )

        self.assertEqual(data, expect)
        copy = transcoder.decode(data)
        self.assertIsInstance(copy, CustomType2)
        self.assertIsInstance(copy.value, CustomType1)
        self.assertIsInstance(copy.value.value, UUID)
        self.assertEqual(copy.value.value, obj.value.value)

        transcoder = JSONTranscoder()
        with self.assertRaises(TypeError) as cm:
            transcoder.decode(data)

        self.assertEqual(
            cm.exception.args[0],
            (
                "Data serialized with name 'uuid_hex' is not deserializable. "
                "Please register a custom transcoding for this type."
            ),
        )
