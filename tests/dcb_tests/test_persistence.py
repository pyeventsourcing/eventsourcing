from abc import ABC, abstractmethod
from typing import Any, ClassVar
from unittest import TestCase

import eventsourcing
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.cryptography import AESCipher
from eventsourcing.dcb.application import DCBRepository
from eventsourcing.dcb.domain import EnduringObject, Event
from eventsourcing.dcb.msgspec import Decision, MsgspecMapper
from eventsourcing.dcb.persistence import DCBEventStore, NotFoundError
from eventsourcing.dcb.popo import InMemoryDCBRecorder
from eventsourcing.persistence import Cipher, Compressor, ProgrammingError
from eventsourcing.utils import Environment


class TestRepository(TestCase):
    def test_repository(self) -> None:
        repo = DCBRepository[Decision](
            DCBEventStore(mapper=MsgspecMapper(), recorder=InMemoryDCBRecorder())
        )
        with self.assertRaises(NotFoundError):
            repo.get("not-an-object", EnduringObject)


class DCBMapperTestCase(TestCase, ABC):
    mapper_class: ClassVar[type[eventsourcing.dcb.persistence.DCBMapper[Any]]]

    def _test_dcb_mapper(self) -> None:
        event = Event(
            tags=["tag1", "tag2"],
            decision=self.construct_decision(),
        )

        mapper = self.construct_mapper()
        dcb_event = mapper.to_dcb_event(event)
        self.assertEqual(dcb_event.tags, event.tags)
        self.assertEqual(dcb_event.uuid, event.uuid)
        self.assertEqual(dcb_event.metadata, event.metadata)

        copy = mapper.to_domain_event(dcb_event)
        self.assertEqual(type(copy), Event)
        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.decision, event.decision)
        self.assertEqual(copy.uuid, event.uuid)
        self.assertEqual(copy.metadata, event.metadata)

        # With compressor
        zlib_compressor = ZlibCompressor()
        mapper = self.construct_mapper(compressor=zlib_compressor)
        dcb_event = mapper.to_dcb_event(event)
        self.assertEqual(dcb_event.tags, event.tags)
        self.assertEqual(dcb_event.uuid, event.uuid)
        self.assertEqual(dcb_event.metadata, event.metadata)

        copy = mapper.to_domain_event(dcb_event)
        self.assertEqual(type(copy), Event)
        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.decision, event.decision)
        self.assertEqual(copy.uuid, event.uuid)
        self.assertEqual(copy.metadata, event.metadata)

        # With cipher
        aes_cipher = AESCipher(
            Environment("", {"CIPHER_KEY": AESCipher.create_key(32)})
        )
        mapper = self.construct_mapper(cipher=aes_cipher)
        dcb_event = mapper.to_dcb_event(event)
        self.assertEqual(dcb_event.tags, event.tags)
        self.assertEqual(dcb_event.uuid, event.uuid)
        self.assertEqual(dcb_event.metadata, event.metadata)

        copy = mapper.to_domain_event(dcb_event)
        self.assertEqual(type(copy), Event)
        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.decision, event.decision)
        self.assertEqual(copy.uuid, event.uuid)
        self.assertEqual(copy.metadata, event.metadata)

        # With compressor and cipher
        mapper = self.construct_mapper(compressor=zlib_compressor, cipher=aes_cipher)
        dcb_event = mapper.to_dcb_event(event)
        self.assertEqual(dcb_event.tags, event.tags)
        self.assertEqual(dcb_event.uuid, event.uuid)
        self.assertEqual(dcb_event.metadata, event.metadata)

        copy = mapper.to_domain_event(dcb_event)
        self.assertEqual(type(copy), Event)
        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.decision, event.decision)
        self.assertEqual(copy.uuid, event.uuid)
        self.assertEqual(copy.metadata, event.metadata)

    @abstractmethod
    def construct_decision(self) -> eventsourcing.dcb.domain.Decision:
        pass

    def construct_mapper(
        self,
        compressor: Compressor | None = None,
        cipher: Cipher | None = None,
    ) -> eventsourcing.dcb.persistence.DCBMapper[Any]:
        return self.mapper_class(compressor=compressor, cipher=cipher)


class TestEventStore(TestCase):
    def test_event_store(self) -> None:
        event_store = DCBEventStore(
            mapper=MsgspecMapper(), recorder=InMemoryDCBRecorder()
        )
        event_store.read()  # no args
        self.assertEqual(0, event_store.append([]))  # no events

        class MyDecision(Decision):
            a: int

        event: Event[Decision] = Event(
            tags=["tag1", "tag2"],
            decision=MyDecision(a=1),
        )
        position = event_store.append([event])
        self.assertEqual(position, 1)
        copies = list(event_store.read())
        self.assertEqual(len(copies), 1)
        copy = copies[0]

        self.assertEqual(type(copy), Event)
        self.assertEqual(copy.tags, event.tags)
        self.assertEqual(copy.decision, event.decision)
        self.assertEqual(copy.uuid, event.uuid)


class TestInMemoryDCBRecorder(TestCase):
    def test_recorder(self) -> None:
        recorder = InMemoryDCBRecorder()
        with self.assertRaises(ProgrammingError):
            recorder.append([])  # no events
