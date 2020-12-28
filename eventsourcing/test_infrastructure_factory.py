import os
from base64 import b64encode
from datetime import datetime
from unittest.case import TestCase
from uuid import uuid4

from eventsourcing.aes import AESCipher
from eventsourcing.utils import get_topic
from eventsourcing.domainevent import DomainEvent
from eventsourcing.eventmapper import (
    DatetimeAsISO,
    DecimalAsStr,
    Mapper,
    Transcoder,
    UUIDAsHex,
)
from eventsourcing.infrastructurefactory import (
    InfrastructureFactory,
)
from eventsourcing.postgresrecorders import (
    PostgresInfrastructureFactory,
)
from eventsourcing.recorders import (
    ApplicationRecorder,
    AggregateRecorder,
    ProcessRecorder,
)
from eventsourcing.sqliterecorders import (
    SQLiteInfrastructureFactory,
)


class InfrastructureFactoryTestCase(TestCase):
    def setUp(self) -> None:
        self.factory = InfrastructureFactory.construct(
            "TestCase"
        )
        self.transcoder = Transcoder()
        self.transcoder.register(UUIDAsHex())
        self.transcoder.register(DecimalAsStr())
        self.transcoder.register(DatetimeAsISO())

    def tearDown(self) -> None:
        # self.factory = None

        for key in [
            InfrastructureFactory.TOPIC,
            InfrastructureFactory.COMPRESSOR_TOPIC,
            InfrastructureFactory.CIPHER_TOPIC,
            InfrastructureFactory.CIPHER_KEY,
        ]:
            try:
                del os.environ[key]
            except KeyError:
                pass

    def test_create_mapper(self):

        # Want to construct:
        #  - application recorder
        #  - snapshot recorder
        #  - mapper
        #  - event store
        #  - snapshot store

        # Want to make configurable:
        #  - cipher (and cipher key)
        #  - compressor
        #  - application recorder class (and db uri, and session)
        #  - snapshot recorder class (and db uri, and session)

        # Common environment:
        #  - factory topic
        #  - cipher topic
        #  - cipher key
        #  - compressor topic

        # POPO environment:

        # SQLite environment:
        #  - database topic
        #  - table name for stored events
        #  - table name for snapshots

        # Create mapper.

        mapper = self.factory.mapper(
            transcoder=self.transcoder,
        )
        self.assertIsInstance(mapper, Mapper)
        self.assertIsNone(mapper.cipher)
        self.assertIsNone(mapper.compressor)

    def test_create_mapper_with_compressor(self):

        # Create mapper with compressor.
        os.environ[self.factory.COMPRESSOR_TOPIC] = "zlib"
        mapper = self.factory.mapper(
            transcoder=self.transcoder
        )
        self.assertIsInstance(mapper, Mapper)
        self.assertIsNone(mapper.cipher)
        self.assertIsNotNone(mapper.compressor)

    def test_create_mapper_with_cipher(self):

        # Check cipher needs a key.
        os.environ[self.factory.CIPHER_TOPIC] = get_topic(
            AESCipher
        )

        with self.assertRaises(EnvironmentError):
            self.factory.mapper(transcoder=self.transcoder)

        cipher_key = AESCipher.create_key(16)
        os.environ[self.factory.CIPHER_KEY] = cipher_key

        # Create mapper with cipher.
        mapper = self.factory.mapper(
            transcoder=self.transcoder
        )
        self.assertIsInstance(mapper, Mapper)
        self.assertIsNotNone(mapper.cipher)
        self.assertIsNone(mapper.compressor)

    def test_create_mapper_with_cipher_and_compressor(
        self,
    ):

        # Create mapper with cipher and compressor.
        os.environ[self.factory.COMPRESSOR_TOPIC] = "zlib"

        os.environ[self.factory.CIPHER_TOPIC] = get_topic(
            AESCipher
        )
        cipher_key = AESCipher.create_key(16)
        os.environ[self.factory.CIPHER_KEY] = cipher_key

        mapper = self.factory.mapper(
            transcoder=self.transcoder
        )
        self.assertIsInstance(mapper, Mapper)
        self.assertIsNotNone(mapper.cipher)
        self.assertIsNotNone(mapper.compressor)

    def test_mapper_with_wrong_cipher_key(self):
        os.environ[self.factory.CIPHER_TOPIC] = get_topic(
            AESCipher
        )
        cipher_key1 = AESCipher.create_key(16)
        cipher_key2 = AESCipher.create_key(16)
        os.environ[
            "APP1_" + self.factory.CIPHER_KEY
        ] = cipher_key1
        os.environ[
            "APP2_" + self.factory.CIPHER_KEY
        ] = cipher_key2

        mapper1: Mapper[DomainEvent] = self.factory.mapper(
            transcoder=self.transcoder,
            application_name="app1",
        )

        mapper2: Mapper = self.factory.mapper(
            transcoder=self.transcoder,
            application_name="app2",
        )
        domain_event = DomainEvent(
            originator_id=uuid4(),
            originator_version=1,
            timestamp=datetime.now(),
        )
        stored_event = mapper1.from_domain_event(
            domain_event
        )
        copy = mapper1.to_domain_event(stored_event)
        self.assertEqual(
            domain_event.originator_id, copy.originator_id
        )

        # This should fail because the infrastructure factory
        # should read different cipher keys from the environment.
        with self.assertRaises(ValueError):
            mapper2.to_domain_event(stored_event)

    def test_create_event_recorder(self):
        recorder = self.factory.aggregate_recorder()
        self.assertIsInstance(recorder, AggregateRecorder)

    def test_create_application_recorder(self):
        recorder = self.factory.application_recorder()
        self.assertIsInstance(
            recorder, ApplicationRecorder
        )

    def test_create_process_recorder(self):

        recorder = self.factory.process_recorder()
        self.assertIsInstance(recorder, ProcessRecorder)


class TestPOPOInfrastructureFactory(
    InfrastructureFactoryTestCase
):
    pass


class TestSQLiteInfrastructureFactory(
    InfrastructureFactoryTestCase
):
    def setUp(self) -> None:
        os.environ[
            InfrastructureFactory.TOPIC
        ] = get_topic(SQLiteInfrastructureFactory)
        os.environ[
            SQLiteInfrastructureFactory.DB_URI
        ] = ":memory:"
        super().setUp()


class TestPostgresInfrastructureFactory(
    InfrastructureFactoryTestCase
):
    def setUp(self) -> None:
        os.environ[
            InfrastructureFactory.TOPIC
        ] = get_topic(PostgresInfrastructureFactory)
        # os.environ[
        #     PostgresInfrastructureFactory.DB_URI
        # ] = ":memory:"
        super().setUp()


del InfrastructureFactoryTestCase
