from __future__ import annotations

from unittest import TestCase
from uuid import uuid4

from eventsourcing.dcb.application import DCBApplication
from eventsourcing.dcb.domain import EnduringObject
from eventsourcing.dcb.msgpack import Decision, MessagePackMapper
from eventsourcing.domain import event, put_metadata_in_context
from eventsourcing.utils import get_topic


class TestDCBApplication(TestCase):
    def test_as_context_manager(self) -> None:
        with DCBApplication():
            pass

    def test_construct_with_env(self) -> None:
        with DCBApplication({"NAME": "value"}) as app:
            self.assertIn("NAME", app.env)

    def test_can_subclass(self) -> None:

        class MyApp1(DCBApplication):
            pass

        app1 = MyApp1()
        self.assertEqual("MyApp1", app1.name)

        class MyApp2(DCBApplication):
            name = "name1"

        app2 = MyApp2()
        self.assertEqual("name1", app2.name)

    def test_respects_metadata(self) -> None:
        class MyEnduringObject(EnduringObject):
            class Created(Decision):
                myenduringobject_id: str

                def apply(self, obj: MyEnduringObject) -> None:
                    obj.created_by = self.metadata["user_id"]

            @event(Created)
            def __init__(self, myenduringobject_id: str):
                self.id = myenduringobject_id
                self.created_by = ""

        with DCBApplication(env={"MAPPER_TOPIC": get_topic(MessagePackMapper)}) as app:
            with put_metadata_in_context({"user_id": "user-1"}):
                obj = MyEnduringObject(myenduringobject_id=str(uuid4()))

            # Check the metadata arrived in the object.
            self.assertEqual(obj.created_by, "user-1")

            # Save the object.
            app.repository.save(obj)

            # Check the metadata arrives in the reconstructed object.
            copy = app.repository.get(obj.id, MyEnduringObject)
            self.assertEqual(copy.created_by, "user-1")

            # Check the events have IDs.
            events = list(app.events.read())
            self.assertEqual(len(events), 1)
            self.assertTrue(events[0].uuid)
