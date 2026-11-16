from decimal import Decimal
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.cipher import AESCipher
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.dataclasses import Decision
from eventsourcing.dataclasses.legacy import (
    DatetimeAsISO,
    DecimalAsStr,
    LegacyJSONTranscoder,
    UUIDAsHex,
)
from eventsourcing.domain import StreamEvent
from eventsourcing.errors import (
    MapperDeserialisationError,
    TranscodingNotRegisteredError,
)
from eventsourcing.persistence import (
    StreamEventMapper,
)
from eventsourcing.tests.bank_account_with_dataclasses import BankAccountWithDataclasses
from eventsourcing.utils import Environment, get_topic


class TestDataclassMapper(TestCase):
    def test_basic_operations(self) -> None:
        # Construct JSONTranscoder.
        transcoder = LegacyJSONTranscoder()
        transcoder.register(UUIDAsHex())
        transcoder.register(DecimalAsStr())
        transcoder.register(DatetimeAsISO())

        # Construct cipher.
        environment = Environment()
        environment[AESCipher.CIPHER_KEY] = AESCipher.create_key(16)
        cipher = AESCipher(environment)

        # Construct compressor.
        compressor = ZlibCompressor()

        # Create a domain event.
        domain_event = StreamEvent[Decision](
            decision=BankAccountWithDataclasses.TransactionAppended(
                amount=Decimal("10.00"),
            ),
            stream_id=str(uuid4()),
            stream_position=123456,
        )

        # Construct mapper with transcoder.
        mapper = StreamEventMapper[Decision](transcoder=transcoder)

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check decrypted copy has correct values.
        assert isinstance(copy.decision, BankAccountWithDataclasses.TransactionAppended)
        self.assertEqual(copy.stream_id, domain_event.stream_id)
        self.assertEqual(copy.stream_position, domain_event.stream_position)
        # TODO: Timestamps...
        # self.assertEqual(copy.timestamp, domain_event.timestamp)
        # self.assertEqual(copy.decision.amount, domain_event.decision.amount)
        self.assertEqual(copy, domain_event)

        # Construct mapper with less capable transcoder.
        mapper = StreamEventMapper(
            transcoder=LegacyJSONTranscoder(),
            cipher=cipher,
        )

        # Check mapper raises MapperDeserialisationError.
        with self.assertRaises(MapperDeserialisationError) as cm:
            mapper.to_domain_event(stored_event)

        # Check the error has useful information about the event.
        self.assertIn(get_topic(type(domain_event.decision)), str(cm.exception))
        self.assertIn(domain_event.stream_id, str(cm.exception))
        self.assertIn(str(domain_event.stream_position), str(cm.exception))

        # Check mapper raises TranscodingNotRegisteredError.
        with self.assertRaises(TranscodingNotRegisteredError):
            mapper.to_stored_event(domain_event)

        # Construct mapper with cipher.
        mapper = StreamEventMapper(transcoder=transcoder, cipher=cipher)

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check values are not visible.
        self.assertNotIn("Alice", str(stored_event.state))

        # Check decrypted copy has correct values.
        self.assertEqual(copy.stream_id, domain_event.stream_id)
        self.assertEqual(copy.stream_position, domain_event.stream_position)

        self.assertEqual(len(stored_event.state), 80)

        # Construct mapper with cipher and compressor.
        mapper = StreamEventMapper(
            transcoder=transcoder,
            cipher=cipher,
            compressor=compressor,
        )

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check decompressed copy has correct values.
        self.assertEqual(copy.stream_id, domain_event.stream_id)
        self.assertEqual(copy.stream_position, domain_event.stream_position)

        self.assertIn(len(stored_event.state), range(50, 100))


# TODO: Move the upcasting tests in here.
