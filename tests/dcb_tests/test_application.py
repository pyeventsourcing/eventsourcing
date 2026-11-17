from __future__ import annotations

from typing import Any, cast, override
from unittest import TestCase
from uuid import uuid4

from eventsourcing import msgspec
from eventsourcing.compressor import ZlibCompressor
from eventsourcing.cryptography import AESCipher
from eventsourcing.dcb.application import BasicDcbApplication
from eventsourcing.dcb.persistence import NotFoundError
from eventsourcing.decorator import event, triggers
from eventsourcing.metadata import get_metadata_from_context, put_metadata_in_context
from eventsourcing.utils import Environment, get_topic


class TestBasicDcbApplication(TestCase):
    def test_as_context_manager(self) -> None:
        with BasicDcbApplication():
            pass

    def test_construct_with_env(self) -> None:
        with BasicDcbApplication(env={"NAME": "value"}) as app:
            self.assertIn("NAME", app.env)

    def test_construct_with_name(self) -> None:
        with BasicDcbApplication(context_name="my_context") as app:
            self.assertEqual(app.context_name, "my_context")
            self.assertIn(cast(Environment, app.env).name, "my_context")

    def test_can_subclass(self) -> None:
        class MyApp1(BasicDcbApplication):
            pass

        app1 = MyApp1()
        self.assertEqual("MyApp1", app1.context_name)

        class MyApp2(BasicDcbApplication):
            context_name = "name1"

        app2 = MyApp2()
        self.assertEqual("name1", app2.context_name)


class TestDcbApplication(TestCase):
    def test_do(self) -> None:
        class Created(msgspec.Decision):
            obj_id: str
            a: str

            @override
            def apply(self, obj: Any) -> None:
                obj.created_by = get_metadata_from_context()["user_id"]

        class Create(msgspec.CommandSlice):
            def __init__(self, obj_id: str, a: str) -> None:
                self.obj_id = obj_id
                self.a = a

            @override
            def consistency_boundary(
                self,
            ) -> msgspec.Selector:
                return msgspec.Selector(types=[Created], tags=[self.obj_id])

            @override
            def execute(self) -> None:
                self.trigger_event(
                    Created,
                    [self.obj_id],
                    a=self.a,
                    obj_id=self.obj_id,
                )

        class Read(msgspec.QuerySlice):
            def __init__(self, obj_id: str):
                self.obj_id = obj_id
                self.a = ""

            @override
            def consistency_boundary(
                self,
            ) -> msgspec.Selector:
                return msgspec.Selector(types=[Created], tags=[self.obj_id])

            @triggers(Created)
            def _(self, a: str) -> None:
                self.a = a

        metadata = {"user_id": "user-1"}
        obj_id = "obj1"
        # Construct an application, and subscribe to the application.
        with (
            msgspec.DcbApplication() as app,
            app.application_subscription(app.recorder.head()) as subscription,
        ):
            with put_metadata_in_context(metadata):
                # Do the 'Create' slice.
                position = app.do(Create(obj_id=obj_id, a="1"))
            # Do the 'Read' slice.
            obj = app.do(Read(obj_id=obj_id))
            # Check the object.
            self.assertEqual("1", obj.a)
            # Receive one event from the subscription.
            recorded_event, tracking = next(subscription)
            # Check the tracking position.
            self.assertEqual(position, tracking.notification_id)
            # Check the recorded metadata.
            self.assertEqual("user-1", recorded_event.metadata["user_id"])
            # Check the recorded decision.
            decision = recorded_event.decision
            self.assertIsInstance(decision, Created)
            assert isinstance(decision, Created)
            self.assertEqual(obj_id, decision.obj_id)
            self.assertEqual("1", decision.a)

    def test_supports_compression(self) -> None:
        env = {
            "COMPRESSOR_TOPIC": get_topic(ZlibCompressor),
        }

        with msgspec.DcbApplication(env=env) as app:
            self.assertTrue(app.mapper.compressor)

    def test_supports_encryption(self) -> None:
        env = {
            "CIPHER_TOPIC": get_topic(AESCipher),
            "CIPHER_KEY": AESCipher.create_key(16),
        }

        with msgspec.DcbApplication(env=env) as app:
            self.assertTrue(app.mapper.cipher)


class TestDcbRepository(TestCase):
    def test_save_and_get(self) -> None:
        class Created(msgspec.Decision):
            obj_id: str

            @override
            def apply(self, obj: MyEnduringObject) -> None:
                obj.created_by = get_metadata_from_context()["user_id"]

        class Updated(msgspec.Decision):
            obj_id: str

        class MyEnduringObject(msgspec.EnduringObject, continuity_id_name="obj_id"):
            @event(Created)
            def __init__(self, obj_id: str):
                self.id = obj_id
                self.created_by = ""

            def update(self) -> None:
                self.trigger_event(
                    Updated,
                    [self.id, "something-else"],
                    obj_id=self.id,
                )

        class MyGroup(msgspec.Group):
            def __init__(self, my_obj: MyEnduringObject | None):
                if my_obj is None:
                    raise NotFoundError
                self.my_obj = my_obj

        metadata = {"user_id": "user-1"}
        with msgspec.DcbApplication() as app:
            # Check get() raises NotFoundError.
            with self.assertRaises(NotFoundError):
                app.repository.get("something-that-does-not-exist", MyEnduringObject)

            # Check get_group() raises NotFoundError.
            with self.assertRaises(NotFoundError):
                app.repository.get_group(MyGroup, "something-that-does-not-exist")

            # Check get_group() returns a list of None.
            copies = app.repository.get_many(
                ["something-that-does-not-exist"], classes=[MyEnduringObject]
            )
            self.assertEqual(1, len(copies))
            self.assertIsNone(copies[0])

            # Construct an enduring object.
            obj_id = str(uuid4())
            with put_metadata_in_context(metadata):
                obj = MyEnduringObject(obj_id=obj_id)
                obj.update()

            # Check the metadata arrived in the object.
            self.assertEqual(obj.created_by, "user-1")

            # Save the object.
            app.repository.save(obj)

            # Check the reconstructed object via the get() method.
            copy = app.repository.get(obj.id, MyEnduringObject)
            self.assertEqual(copy.created_by, "user-1")

            # Check the reconstructed object via the get_many() method (classes arg).
            copies = app.repository.get_many([obj.id], classes=[MyEnduringObject])
            self.assertEqual(cast(MyEnduringObject, copies[0]).created_by, "user-1")

            # Check the reconstructed object via the get_many() method (cls arg).
            copies = app.repository.get_many([obj.id], cls=MyEnduringObject)
            self.assertEqual(cast(MyEnduringObject, copies[0]).created_by, "user-1")

            # Check the reconstructed group.
            group = app.repository.get_group(MyGroup, obj.id)
            self.assertIsInstance(group, MyGroup)
            self.assertEqual(group.my_obj.id, obj_id)
            self.assertEqual(cast(MyEnduringObject, copies[0]).created_by, "user-1")

            # Check the events have IDs and metadata.
            events = list(app.events.read())
            self.assertEqual(len(events), 2)
            self.assertTrue(events[0].event_id)
            self.assertEqual(metadata, events[0].metadata)
