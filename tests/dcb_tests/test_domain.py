from typing import Any
from unittest import TestCase

from eventsourcing.dcb.domain import (
    DecoratedFuncCaller,
    EnduringObject,
    Initialises,
    Mutates,
)
from eventsourcing.domain import ProgrammingError, event


class TestEnduringObject(TestCase):
    def test_subclass_requires_nested_initialiser(self) -> None:
        class MyObj(EnduringObject[Mutates]):
            pass

        with self.assertRaisesRegex(ProgrammingError, "Please define"):
            MyObj()

    def test_subclass_initialiser_attributes_must_match(self) -> None:
        class MyObj(EnduringObject[Mutates]):
            def __init__(self, a: str) -> None:
                self.a = a

            class Created(Initialises):
                pass

        with self.assertRaisesRegex(
            TypeError, f"Unable to construct {MyObj.Created.__qualname__}"
        ):
            MyObj(a="a")

    def test_nice_error_when_initialiser_cannot_construct_enduring_object(self) -> None:
        class MyObj(EnduringObject[Mutates]):
            def __init__(self) -> None:
                pass

            class Created(Initialises):
                def __init__(
                    self, myobj_id: str, originator_topic: str, tags: list[str], a: str
                ) -> None:
                    self.myobj_id = myobj_id
                    self.originator_topic = originator_topic
                    self.a = a

                def _as_dict(self) -> dict[str, Any]:
                    return self.__dict__

        with self.assertRaisesRegex(TypeError, "Unable to construct"):
            MyObj(a="a")  # type: ignore[call-arg]

    def test_subclassed_events_set_on_enduring_object(self) -> None:
        class MyObj(EnduringObject[Mutates]):
            def __init__(self) -> None:
                pass

            class MyInitialDecision(Initialises):
                def __init__(self, originator_topic: str, myobj_id: str) -> None:
                    self.originator_topic = originator_topic
                    self.myobj_id = myobj_id

                def _as_dict(self) -> dict[str, Any]:
                    return self.__dict__

            class MyDecision(Mutates):
                def __init__(self) -> None:
                    pass

                def _as_dict(self) -> dict[str, Any]:
                    return self.__dict__

            @event(MyDecision)
            def my_command(self) -> None:
                pass

        myobj = MyObj()
        self.assertTrue(issubclass(myobj.MyDecision, DecoratedFuncCaller))
