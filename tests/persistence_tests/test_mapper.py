from decimal import Decimal
from unittest.case import TestCase
from uuid import UUID, uuid4

from eventsourcing.cipher import AESCipher
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.domain import (
    CanMutateAggregate,
    HasOriginatorIDVersion,
)
from eventsourcing.persistence import (
    DataclassMapper,
    DatetimeAsISO,
    DecimalAsStr,
    JSONTranscoder,
    MapperDeserialisationError,
    TranscodingNotRegisteredError,
    UUIDAsHex,
    find_id_convertor,
    pass_through_convertor,
    str_to_uuid_convertor,
)
from eventsourcing.tests.domain import BankAccount
from eventsourcing.utils import Environment, get_topic


class TestDataclassMapper(TestCase):
    def test_basic_operations(self) -> None:
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

        # Create a domain event.
        domain_event = BankAccount.TransactionAppended(
            originator_id=uuid4(),
            originator_version=123456,
            amount=Decimal("10.00"),
        )

        # Construct mapper with transcoder.
        mapper = DataclassMapper[UUID](transcoder=transcoder)

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check decrypted copy has correct values.
        assert isinstance(copy, BankAccount.TransactionAppended)
        self.assertEqual(copy.originator_id, domain_event.originator_id)
        self.assertEqual(copy.originator_version, domain_event.originator_version)
        self.assertEqual(copy.timestamp, domain_event.timestamp)
        self.assertEqual(copy.amount, domain_event.amount)
        self.assertEqual(copy, domain_event)

        # Construct mapper with less capable transcoder.
        mapper = DataclassMapper(
            transcoder=JSONTranscoder(),
            cipher=cipher,
        )

        # Check mapper raises MapperDeserialisationError.
        with self.assertRaises(MapperDeserialisationError) as cm:
            mapper.to_domain_event(stored_event)

        # Check the error has useful information about the event.
        self.assertIn(get_topic(type(domain_event)), str(cm.exception))
        self.assertIn(str(domain_event.originator_id), str(cm.exception))
        self.assertIn(str(domain_event.originator_version), str(cm.exception))

        # Check mapper raises TranscodingNotRegisteredError.
        with self.assertRaises(TranscodingNotRegisteredError):
            mapper.to_stored_event(domain_event)

        # Construct mapper with cipher.
        mapper = DataclassMapper(transcoder=transcoder, cipher=cipher)

        # Map to stored event.
        stored_event = mapper.to_stored_event(domain_event)

        # Map to domain event.
        copy = mapper.to_domain_event(stored_event)

        # Check values are not visible.
        self.assertNotIn("Alice", str(stored_event.state))

        # Check decrypted copy has correct values.
        self.assertEqual(copy.originator_id, domain_event.originator_id)
        self.assertEqual(copy.originator_version, domain_event.originator_version)

        self.assertEqual(len(stored_event.state), 176)

        # Construct mapper with cipher and compressor.
        mapper = DataclassMapper(
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

        self.assertIn(len(stored_event.state), range(100, 200))

    def test_find_id_convertor(self) -> None:
        class HasUuidID(HasOriginatorIDVersion[UUID]):
            pass

        self.assertIs(find_id_convertor(HasUuidID, UUID), pass_through_convertor)

        self.assertIs(find_id_convertor(HasUuidID, str), str_to_uuid_convertor)

        class HasStringID(HasOriginatorIDVersion[str]):
            pass

        self.assertIs(find_id_convertor(HasStringID, UUID), pass_through_convertor)

        self.assertIs(find_id_convertor(HasStringID, str), pass_through_convertor)

        # Check raises if no type arg have been provided.
        with self.assertRaises(TypeError) as cm:
            self.assertIs(
                find_id_convertor(HasOriginatorIDVersion, str), pass_through_convertor
            )

        self.assertIn("originator_id_type cannot be None", str(cm.exception))

        # Check raises if no type arg has been provided.
        with self.assertRaises(TypeError) as cm:
            self.assertIs(
                find_id_convertor(CanMutateAggregate, str), pass_through_convertor
            )

        self.assertIn("originator_id_type cannot be None", str(cm.exception))

        # Check raises if no type arg has been provided.
        class HasNoneID(HasOriginatorIDVersion):  # type: ignore[type-arg]
            pass

        with self.assertRaises(TypeError) as cm:
            self.assertIs(find_id_convertor(HasNoneID, str), pass_through_convertor)

        self.assertIn("originator_id_type cannot be None", str(cm.exception))

        # Check UUID annotation.
        class HasAnnotationUUID:
            originator_id: UUID

        self.assertIs(
            find_id_convertor(HasAnnotationUUID, UUID), pass_through_convertor
        )

        self.assertIs(find_id_convertor(HasAnnotationUUID, str), str_to_uuid_convertor)

        # Check str annotation.
        class HasAnnotationStr:
            originator_id: str

        self.assertIs(find_id_convertor(HasAnnotationStr, UUID), pass_through_convertor)

        self.assertIs(find_id_convertor(HasAnnotationStr, str), pass_through_convertor)

        # Check raises if annotation invalid.
        class HasAnnotationInt:
            originator_id: int

        with self.assertRaises(TypeError) as cm:
            find_id_convertor(HasAnnotationInt, str)

        self.assertIn(
            "is not either UUID or str",
            str(cm.exception),
        )

        # Check raises if without annotation.
        class WithoutAnnotation:
            pass

        with self.assertRaises(TypeError) as cm:
            find_id_convertor(WithoutAnnotation, str)

        self.assertIn(
            "nor its bases have an originator_id annotation",
            str(cm.exception),
        )

    def test_convertors(self) -> None:
        self.assertIsInstance(pass_through_convertor(""), str)
        self.assertIsInstance(pass_through_convertor(uuid4()), UUID)
        self.assertIsInstance(str_to_uuid_convertor(str(uuid4())), UUID)


# TODO: Move the upcasting tests in here.
