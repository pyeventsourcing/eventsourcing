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
from eventsourcing.domain import AggregateEvent
from eventsourcing.errors import (
    MapperDeserialisationError,
    TranscodingNotRegisteredError,
)
from eventsourcing.persistence import (
    AggregateEventMapper,
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
        domain_event = AggregateEvent[Decision](
            decision=BankAccountWithDataclasses.TransactionAppended(
                amount=Decimal("10.00"),
            ),
            originator_id=str(uuid4()),
            originator_version=123456,
        )

        # Construct mapper with transcoder.
        mapper = AggregateEventMapper[Decision](transcoder=transcoder)

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check decrypted copy has correct values.
        assert isinstance(copy.decision, BankAccountWithDataclasses.TransactionAppended)
        self.assertEqual(copy.originator_id, domain_event.originator_id)
        self.assertEqual(copy.originator_version, domain_event.originator_version)
        # TODO: Timestamps...
        # self.assertEqual(copy.timestamp, domain_event.timestamp)
        # self.assertEqual(copy.decision.amount, domain_event.decision.amount)
        self.assertEqual(copy, domain_event)

        # Construct mapper with less capable transcoder.
        mapper = AggregateEventMapper(
            transcoder=LegacyJSONTranscoder(),
            cipher=cipher,
        )

        # Check mapper raises MapperDeserialisationError.
        with self.assertRaises(MapperDeserialisationError) as cm:
            mapper.to_domain_event(stored_event)

        # Check the error has useful information about the event.
        self.assertIn(get_topic(type(domain_event.decision)), str(cm.exception))
        self.assertIn(domain_event.originator_id, str(cm.exception))
        self.assertIn(str(domain_event.originator_version), str(cm.exception))

        # Check mapper raises TranscodingNotRegisteredError.
        with self.assertRaises(TranscodingNotRegisteredError):
            mapper.to_stored_event(domain_event)

        # Construct mapper with cipher.
        mapper = AggregateEventMapper(transcoder=transcoder, cipher=cipher)

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check values are not visible.
        self.assertNotIn("Alice", str(stored_event.state))

        # Check decrypted copy has correct values.
        self.assertEqual(copy.originator_id, domain_event.originator_id)
        self.assertEqual(copy.originator_version, domain_event.originator_version)

        self.assertEqual(len(stored_event.state), 80)

        # Construct mapper with cipher and compressor.
        mapper = AggregateEventMapper(
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

        self.assertIn(len(stored_event.state), range(50, 100))

    # def test_convertors(self) -> None:
    #     self.assertIsInstance(pass_through_convertor(""), str)
    #     self.assertIsInstance(pass_through_convertor(uuid4()), UUID)
    #     self.assertIsInstance(str_to_uuid_convertor(str(uuid4())), UUID)
    #
    # def test_default_to_database_generated_event_id(self) -> None:
    #     # Construct mapper with transcoder.
    #     transcoder = JSONTranscoder()
    #     transcoder.register(UUIDAsHex())
    #     transcoder.register(DecimalAsStr())
    #     transcoder.register(DatetimeAsISO())
    #     mapper = AggregateEventMapper(transcoder=transcoder)
    #
    #     # Create a domain event.
    #     domain_event = AggregateEvent(
    #         decision=BankAccountWithDataclasses.TransactionAppended(
    #             amount=Decimal("10.00"),
    #         ),
    #         originator_id=uuid4(),
    #         originator_version=123456,
    #     )
    #
    #     # Map to stored event.
    #     stored_event = mapper.to_stored_event(domain_event)
    #
    #     # Remove `event_id` from serialised state.
    #     modified_state = json.loads(stored_event.state.decode())
    #     modified_state.pop("event_id")
    #
    #     # Set `event_id` on StoredEvent (as if database-generated).
    #     event_id = uuid4()
    #     modified_stored_event = StoredEvent(
    #         originator_id=stored_event.originator_id,
    #         originator_version=stored_event.originator_version,
    #         topic=stored_event.topic,
    #         state=json.dumps(modified_state).encode(),
    #         event_id=event_id,
    #     )
    #
    #     # Map to domain event.
    #     copy = mapper.to_domain_event(modified_stored_event)
    #
    #     # Check copy has correct values.
    #     self.assertEqual(copy.event_id, event_id)
    #     assert isinstance(copy, BankAccountWithDataclasses.TransactionAppended)
    #     self.assertEqual(copy.originator_id, domain_event.originator_id)
    #     self.assertEqual(copy.originator_version, domain_event.originator_version)
    #     self.assertEqual(copy.timestamp, domain_event.timestamp)
    #     self.assertEqual(copy.amount, domain_event.amount)


# TODO: Move the upcasting tests in here.
