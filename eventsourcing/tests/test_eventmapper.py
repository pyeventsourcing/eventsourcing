from datetime import datetime
from decimal import Decimal
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.cipher import AESCipher
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.domain import TZINFO
from eventsourcing.persistence import (
    DatetimeAsISO,
    DecimalAsStr,
    JSONTranscoder,
    Mapper,
    Transcoding,
    UUIDAsHex,
)
from eventsourcing.tests.test_aggregate import BankAccount


class TestMapper(TestCase):
    def test(self):
        # Construct transcoder.
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

        # Construct cipher.
        cipher = AESCipher(cipher_key=AESCipher.create_key(16))

        # Construct compressor.
        compressor = ZlibCompressor()

        # Construct mapper with cipher.
        mapper = Mapper(transcoder=transcoder, cipher=cipher)

        # Create a domain event.
        domain_event = BankAccount.TransactionAppended(
            originator_id=uuid4(),
            originator_version=123456,
            timestamp=datetime.now(tz=TZINFO),
            amount=Decimal("10.00"),
        )

        # Map from domain event.
        stored_event = mapper.from_domain_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check values are not visible.
        assert "Alice" not in str(stored_event.state)

        # Check decrypted copy has correct values.
        assert copy.originator_id == domain_event.originator_id
        assert copy.originator_version == domain_event.originator_version
        assert copy.timestamp == domain_event.timestamp, copy.timestamp
        assert copy.originator_version == domain_event.originator_version

        assert len(stored_event.state) == 171, len(stored_event.state)

        # Construct mapper with cipher and compressor.
        mapper = Mapper(
            transcoder=transcoder,
            cipher=cipher,
            compressor=compressor,
        )

        # Map from domain event.
        stored_event = mapper.from_domain_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check decompressed copy has correct values.
        assert copy.originator_id == domain_event.originator_id
        assert copy.originator_version == domain_event.originator_version

        assert len(stored_event.state) in (
            135,
            136,
            137,
            138,
            139,
            140,
            141,
            142,
            143,
        ), len(stored_event.state)


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


class TestTranscoder(TestCase):
    def test(self):
        transcoder = JSONTranscoder()
        obj = CustomType2(CustomType1(UUID("b2723fe2c01a40d2875ea3aac6a09ff5")))
        with self.assertRaises(TypeError) as cm:
            transcoder.encode(obj)

        self.assertEqual(
            cm.exception.args[0],
            (
                "Object of type <class 'eventsourcing.tests.test_eventmapper."
                "CustomType2'> is not serializable. Please define and register "
                "a custom transcoding for this type."
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
