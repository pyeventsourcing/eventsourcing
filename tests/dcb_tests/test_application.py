from __future__ import annotations

from unittest import TestCase
from uuid import uuid4

from eventsourcing.compressor import ZlibCompressor
from eventsourcing.cryptography import AESCipher
from eventsourcing.dcb.application import DCBApplication
from eventsourcing.domain import (
    EnduringObject,
    event,
    get_metadata_from_context,
    put_metadata_in_context,
)
from eventsourcing.msgspec.application import MsgspecDCBApplication
from eventsourcing.msgspec.immutable import MsgspecDecision
from eventsourcing.utils import get_topic


class TestDCBApplication(TestCase):
    def test_as_context_manager(self) -> None:
        with DCBApplication():
            pass

    def test_construct_with_env(self) -> None:
        with DCBApplication[MsgspecDecision]({"NAME": "value"}) as app:
            self.assertIn("NAME", app.env)

    def test_can_subclass(self) -> None:

        class MyApp1(DCBApplication[MsgspecDecision]):
            pass

        app1 = MyApp1()
        self.assertEqual("MyApp1", app1.name)

        class MyApp2(DCBApplication[MsgspecDecision]):
            name = "name1"

        app2 = MyApp2()
        self.assertEqual("name1", app2.name)

    def test_respects_metadata(self) -> None:
        class MyEnduringObject(EnduringObject[MsgspecDecision]):
            class Created(MsgspecDecision):
                my_enduring_object_id: str

                def apply(self, obj: MyEnduringObject) -> None:
                    obj.created_by = get_metadata_from_context()["user_id"]

            @event(Created)
            def __init__(self, my_enduring_object_id: str):
                self.id = my_enduring_object_id
                self.created_by = ""

        metadata = {"user_id": "user-1"}
        with MsgspecDCBApplication() as app:
            with put_metadata_in_context(metadata):
                obj = MyEnduringObject(my_enduring_object_id=str(uuid4()))

            # Check the metadata arrived in the object.
            self.assertEqual(obj.created_by, "user-1")

            # Save the object.
            app.repository.save(obj)

            # Check the metadata arrives in the reconstructed object.
            copy = app.repository.get(obj.id, MyEnduringObject)
            self.assertEqual(copy.created_by, "user-1")

            # Check the events have IDs and metadata.
            events = list(app.events.read())
            self.assertEqual(len(events), 1)
            self.assertTrue(events[0].uuid)
            self.assertEqual(metadata, events[0].metadata)

    def test_supports_compression(self) -> None:
        env = {
            "COMPRESSOR_TOPIC": get_topic(ZlibCompressor),
        }

        with MsgspecDCBApplication(env) as app:
            self.assertTrue(app.mapper.compressor)

    def test_supports_encryption(self) -> None:
        env = {
            "CIPHER_TOPIC": get_topic(AESCipher),
            "CIPHER_KEY": AESCipher.create_key(16),
        }

        with MsgspecDCBApplication(env) as app:
            self.assertTrue(app.mapper.cipher)
