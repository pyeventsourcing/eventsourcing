import warnings
from decimal import Decimal
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.cipher import AESCipher
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.domain import AggregateEvent
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

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check values are not visible.
        self.assertNotIn("Alice", str(stored_event.state))

        # Check decrypted copy has correct values.
        self.assertEqual(copy.originator_id, domain_event.originator_id)
        self.assertEqual(copy.originator_version, domain_event.originator_version)
        self.assertEqual(copy.timestamp, domain_event.timestamp)
        self.assertEqual(copy.originator_version, domain_event.originator_version)

        self.assertEqual(len(stored_event.state), 162)

        # Construct mapper with cipher and compressor.
        mapper = Mapper(
            transcoder=transcoder,
            cipher=cipher,
            compressor=compressor,
        )

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check decompressed copy has correct values.
        self.assertEqual(copy.originator_id, domain_event.originator_id)
        self.assertEqual(copy.originator_version, domain_event.originator_version)

        self.assertIn(len(stored_event.state), range(129, 143))

    def test_from_domain_event_gives_deprecated_warning(self):
        # Construct transcoder.
        transcoder = JSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DatetimeAsISO())

        # Construct mapper with cipher.
        mapper = Mapper(transcoder=transcoder)

        # Create a domain event.
        domain_event = AggregateEvent(
            originator_id=uuid4(),
            originator_version=123456,
            timestamp=AggregateEvent.create_timestamp(),
        )

        # Verify deprecation warning.
        with warnings.catch_warnings(record=True) as w:
            stored_event = mapper.from_domain_event(domain_event)

        self.assertEqual(len(w), 1)
        self.assertIs(w[-1].category, DeprecationWarning)
        self.assertEqual(
            "'from_domain_event()' is deprecated, use 'to_stored_event()' instead",
            w[-1].message.args[0],
        )

        self.assertEqual(stored_event.originator_id, domain_event.originator_id)
        self.assertEqual(
            stored_event.originator_version, domain_event.originator_version
        )
