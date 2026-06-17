from unittest import TestCase
from uuid import uuid4

from pydantic import ValidationError

from eventsourcing.domain import datetime_now_with_tzinfo
from examples.aggregate8.mutablemodel import AggregateSnapshot, SnapshotState


class TestSnapshotState(TestCase):
    def test_raises_type_error_if_not_subclass_of_snapshot_state(self) -> None:
        # state defined with wrong type - not okay
        with self.assertRaises(TypeError) as cm:

            class MyBrokenSnapshot(AggregateSnapshot):
                state: int

        self.assertTrue(
            str(cm.exception).endswith("got: <class 'int'>"),
            str(cm.exception),
        )

        class MySnapshotState(SnapshotState):
            a: str

        # state not defined - not okay
        with self.assertRaises(TypeError) as cm:

            class MyMisspelledSnapshot(AggregateSnapshot):
                misspelled: MySnapshotState

        self.assertTrue(
            str(cm.exception).endswith("got: typing.Any"),
            str(cm.exception),
        )

        # this is okay
        class MySnapshot(AggregateSnapshot):
            state: MySnapshotState

        snapshot = MySnapshot(
            originator_id=uuid4(),
            originator_version=1,
            topic="",
            state=MySnapshotState(
                a="a",
                _created_on=datetime_now_with_tzinfo(),  # pyright: ignore[reportCallIssue]
                _modified_on=datetime_now_with_tzinfo(),  # pyright: ignore[reportCallIssue]
            ),
        )

        with self.assertRaises(ValidationError):
            # It's frozen.
            snapshot.state.a = "b"  # type: ignore[misc]
