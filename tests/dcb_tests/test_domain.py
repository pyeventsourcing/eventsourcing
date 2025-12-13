from dataclasses import dataclass
from unittest import TestCase

from eventsourcing.dcb.domain import (
    Decision,
    DecoratedFuncCaller,
    EnduringObject,
    InitialDecision,
)
from eventsourcing.domain import ProgrammingError, event
from eventsourcing.utils import get_topic


class TestEnduringObject(TestCase):
    def test_subclass_requires_nested_initialiser(self) -> None:
        class MyObj(EnduringObject[Decision]):
            pass

        with self.assertRaisesRegex(ProgrammingError, "Please define"):
            MyObj()

    def test_subclass_initialiser_attributes_must_match(self) -> None:
        class MyObj(EnduringObject[Decision]):
            def __init__(self, a: str) -> None:
                self.a = a

            class Created(InitialDecision):
                pass

        with self.assertRaisesRegex(
            TypeError, f"Unable to construct {MyObj.Created.__qualname__}"
        ):
            MyObj(a="a")

    def test_nice_error_when_initialiser_cannot_construct_enduring_object(self) -> None:
        class MyObj(EnduringObject[Decision]):
            def __init__(self) -> None:
                pass

            class Created(InitialDecision):
                def __init__(
                    self, myobj_id: str, originator_topic: str, tags: list[str], a: str
                ) -> None:
                    self.myobj_id = myobj_id
                    self.originator_topic = originator_topic
                    self.a = a

        with self.assertRaisesRegex(TypeError, "Unable to construct"):
            MyObj(a="a")  # type: ignore[call-arg]

    def test_subclassed_events_set_on_enduring_object(self) -> None:
        class MyObj(EnduringObject[Decision]):
            def __init__(self) -> None:
                pass

            class MyInitialDecision(InitialDecision):
                def __init__(self, originator_topic: str, myobj_id: str) -> None:
                    self.originator_topic = originator_topic
                    self.myobj_id = myobj_id

            class MyDecision(Decision):
                pass

            @event(MyDecision)
            def my_command(self) -> None:
                pass

        myobj = MyObj()
        self.assertTrue(issubclass(myobj.MyDecision, DecoratedFuncCaller))

    def test_initial_decision_mutate_raises_type_error(self) -> None:

        @dataclass
        class MyInitialDecision(InitialDecision):
            originator_topic: str

        decision = MyInitialDecision(originator_topic=get_topic(type(self)))
        with self.assertRaises(TypeError) as cm:
            decision.mutate(None)

        self.assertTrue(
            "Originator type not subclass of EnduringObject" in str(cm.exception)
        )
