from decimal import Decimal
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.cipher import AESCipher
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.persistence import (
    DatetimeAsISO,
    DecimalAsStr,
    JSONTranscoder,
    Mapper,
    UUIDAsHex,
)
from eventsourcing.tests.domain import BankAccount
from eventsourcing.utils import Environment


class TestMapper(TestCase):
    def test(self):
        # Construct transcoder.
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

        # Construct cipher.
        environment = Environment()
        environment[AESCipher.CIPHER_KEY] = AESCipher.create_key(16)
        cipher = AESCipher(environment)

        # Construct compressor.
        compressor = ZlibCompressor()

        # Construct mapper with cipher.
        mapper = Mapper(transcoder=transcoder, cipher=cipher)

        # Create a domain event.
        domain_event = BankAccount.TransactionAppended(
            originator_id=uuid4(),
            originator_version=123456,
            timestamp=BankAccount.TransactionAppended.create_timestamp(),
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

        assert len(stored_event.state) == 162, len(stored_event.state)

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
