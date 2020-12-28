from datetime import datetime
from decimal import Decimal
from typing import Union
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.aes import AESCipher
from eventsourcing.aggregate import BankAccount
from eventsourcing.eventmapper import (
    DatetimeAsISO,
    DecimalAsStr,
    Mapper,
    Transcoder,
    Transcoding,
    UUIDAsHex,
)


class TestMapper(TestCase):
    def test(self):
        # Construct transcoder.
        transcoder = Transcoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

        # Construct cipher.
        cipher = AESCipher(cipher_key=AESCipher.create_key(16))

        # Construct mapper with cipher.
        mapper = Mapper(
            transcoder=transcoder, cipher=cipher
        )

        # Create a domain event.
        domain_event = BankAccount.TransactionAppended(
            originator_id=uuid4(),
            originator_version=123456,
            timestamp=datetime.now(),
            amount=Decimal("10.00"),
        )

        # Map from domain event.
        stored_event = mapper.from_domain_event(
            domain_event
        )

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check values are not visible.
        assert "Alice" not in str(stored_event.state)

        # Check decrypted copy has correct values.
        assert (
            copy.originator_id
            == domain_event.originator_id
        )
        assert (
            copy.originator_version
            == domain_event.originator_version
        )
        assert (
            copy.timestamp == domain_event.timestamp
        ), copy.timestamp
        assert (
            copy.originator_version
            == domain_event.originator_version
        )

        assert len(stored_event.state) == 173, len(
            stored_event.state
        )

        import zlib

        # Construct mapper with cipher and compressor.
        mapper = Mapper(
            transcoder=transcoder,
            cipher=cipher,
            compressor=zlib,
        )

        # Map from domain event.
        stored_event = mapper.from_domain_event(
            domain_event
        )

        # Check decompressed copy has correct values.
        assert (
            copy.originator_id
            == domain_event.originator_id
        )
        assert (
            copy.originator_version
            == domain_event.originator_version
        )

        assert len(stored_event.state) in (
            134,
            135,
            136,
            137,
            138,
            139,
            140,
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

    def encode(self, o: CustomType1) -> dict:
        return {"value": o.value}

    def decode(self, d: Union[str, dict]) -> CustomType1:
        assert isinstance(d, dict)
        return CustomType1(d["value"])


class CustomType2AsDict(Transcoding):
    type = CustomType2
    name = "custom_type2_as_dict"

    def encode(self, o: CustomType1) -> dict:
        return {"value": o.value}

    def decode(self, d: Union[str, dict]) -> CustomType2:
        assert isinstance(d, dict)
        return CustomType2(d["value"])


class TestTranscoder(TestCase):
    def test(self):
        transcoder = Transcoder()
        obj = CustomType2(
            CustomType1(
                UUID("b2723fe2c01a40d2875ea3aac6a09ff5")
            )
        )
        with self.assertRaises(TypeError):
            transcoder.encode(obj)

        transcoder.register(UUIDAsHex())
        transcoder.register(CustomType1AsDict())
        transcoder.register(CustomType2AsDict())

        data = transcoder.encode(obj)
        expect = (
            b'{"__type__": "custom_type2_as_dict", "__data__": {"value": '
            b'{"__type__": "custom_type1_as_dict", "__data__": {"value": '
            b'{"__type__": "uuid_hex", "__data__": "b2723fe2c01a40d2875ea'
            b'3aac6a09ff5"}}}}}'
        )
        self.assertEqual(data, expect)
        copy = transcoder.decode(data)
        self.assertIsInstance(copy, CustomType2)
        self.assertIsInstance(copy.value, CustomType1)
        self.assertIsInstance(copy.value.value, UUID)
        self.assertEqual(copy.value.value, obj.value.value)
