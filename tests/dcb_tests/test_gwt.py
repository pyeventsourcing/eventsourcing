from unittest import TestCase

from eventsourcing.dataclasses import Decision, Selector, Slice
from eventsourcing.dcb.gwt import given
from eventsourcing.domain import TaggedEvent, triggers


class TestGivenWhenThen(TestCase):
    def test_gwt_flow(self) -> None:
        class MyDecision(Decision):
            pass

        class MySlice(Slice):
            def __init__(self, obj_id: str):
                self.obj_id = obj_id
                self.executed = False

            def consistency_boundary(self) -> Selector:
                return Selector(types=[MyDecision], tags=[self.obj_id])

            def execute(self) -> None:
                self.trigger_event(MyDecision)
                self.executed = True

        # 1. Given an event that matches the boundary
        obj_id = "123"
        event = TaggedEvent(decision=MyDecision(), tags=[obj_id])

        # 2. When we execute a slice
        slice_ = MySlice(obj_id=obj_id)
        when = given(event).when(slice_)

        # 3. Then we should see the expected results
        # The execute method should have been called automatically
        self.assertTrue(slice_.executed)

        # Test .then() assertion with TaggedEvent
        expected_event = TaggedEvent(decision=MyDecision(), tags=[])
        when.then(expected_event)

    def test_boundary_mismatch_raises_assertion_error(self) -> None:
        class MyDecision(Decision):
            pass

        class MySlice(Slice):
            def consistency_boundary(self) -> Selector:
                return Selector(types=[MyDecision], tags=["123"])

            def execute(self) -> None:
                pass

        # Event with different tag
        event = TaggedEvent(decision=MyDecision(), tags=["456"])

        slice_ = MySlice()

        with self.assertRaises(AssertionError) as cm:
            given(event).when(slice_)
        self.assertIn("Consistency boundary wouldn't have selected", str(cm.exception))

    def test_then_assertion_failure(self) -> None:
        class MyDecision(Decision):
            pass

        class OtherDecision(Decision):
            pass

        class MySlice(Slice):
            def consistency_boundary(self) -> Selector:
                return Selector(types=[MyDecision])

            def execute(self) -> None:
                self.trigger_event(MyDecision)

        when = given(TaggedEvent(decision=MyDecision(), tags=[])).when(MySlice())

        with self.assertRaises(AssertionError):
            when.then(TaggedEvent(decision=OtherDecision(), tags=[]))

    def test_multiple_events(self) -> None:
        class MyDecision(Decision):
            pass

        class MySlice(Slice):
            def consistency_boundary(self) -> Selector:
                return Selector(types=[MyDecision])

            def execute(self) -> None:
                self.trigger_event(MyDecision)
                self.trigger_event(MyDecision)

        event = TaggedEvent(decision=MyDecision(), tags=[])
        when = given(event).when(MySlice())

        when.then(
            TaggedEvent(decision=MyDecision(), tags=[]),
            TaggedEvent(decision=MyDecision(), tags=[]),
        )

    def test_multiple_selectors_in_boundary(self) -> None:
        class Decision1(Decision):
            pass

        class Decision2(Decision):
            pass

        class MySlice(Slice):
            def consistency_boundary(self) -> list[Selector]:
                return [Selector(types=[Decision1]), Selector(types=[Decision2])]

            def execute(self) -> None:
                pass

        # Matches first selector
        event1 = TaggedEvent(decision=Decision1(), tags=[])
        given(event1).when(MySlice()).then()

        # Matches second selector
        event2 = TaggedEvent(decision=Decision2(), tags=[])
        given(event2).when(MySlice()).then()

        # Matches neither
        class Decision3(Decision):
            pass

        event3 = TaggedEvent(decision=Decision3(), tags=[])
        with self.assertRaises(AssertionError):
            given(event3).when(MySlice())

    def test_selector_matches_all_if_empty(self) -> None:
        class MyDecision(Decision):
            pass

        class MySlice(Slice):
            def consistency_boundary(self) -> Selector:
                # Empty selector matches everything
                return Selector()

            def execute(self) -> None:
                pass

        event = TaggedEvent(decision=MyDecision(), tags=["any"])
        given(event).when(MySlice()).then()

    def test_slice_projection(self) -> None:
        class MyDecision(Decision):
            obj_id: str
            value: int

        class MySlice(Slice):
            def __init__(self, obj_id: str):
                self.obj_id = obj_id
                self.total = 0

            def consistency_boundary(self) -> Selector:
                return Selector(types=[MyDecision], tags=[self.obj_id])

            @triggers(MyDecision)
            def apply_decision(self, value: int) -> None:
                self.total += value

            def execute(self) -> None:
                if self.total > 10:
                    self.trigger_event(MyDecision, obj_id=self.obj_id, value=100)

        obj_id = "123"
        event1 = TaggedEvent(decision=MyDecision(obj_id=obj_id, value=5), tags=[obj_id])
        event2 = TaggedEvent(decision=MyDecision(obj_id=obj_id, value=6), tags=[obj_id])

        # total = 5 + 6 = 11 > 10, so it should trigger another event
        when = given(event1, event2).when(MySlice(obj_id=obj_id))

        when.then(TaggedEvent(decision=MyDecision(obj_id=obj_id, value=100), tags=[]))

    def test_then_assertion_failures(self) -> None:
        class MyDecision(Decision):
            pass

        class MySlice(Slice):
            def consistency_boundary(self) -> Selector:
                return Selector()

            def execute(self) -> None:
                self.trigger_event(MyDecision, ["tag1"])

        when = given(TaggedEvent(decision=MyDecision(), tags=[])).when(MySlice())

        # Length mismatch
        with self.assertRaises(AssertionError) as cm:
            when.then()
        self.assertIn("Expected 0 events, got 1", str(cm.exception))

        # Decision mismatch
        class OtherDecision(Decision):
            pass

        with self.assertRaises(AssertionError) as cm:
            when.then(TaggedEvent(decision=OtherDecision(), tags=["tag1"]))
        self.assertIn("decision mismatch", str(cm.exception))

        # Tags mismatch
        with self.assertRaises(AssertionError) as cm:
            when.then(TaggedEvent(decision=MyDecision(), tags=["tag2"]))
        self.assertIn("tags mismatch", str(cm.exception))
