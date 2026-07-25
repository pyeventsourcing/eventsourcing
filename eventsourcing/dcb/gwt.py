from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from eventsourcing.domain import AbstractDecision, Selector, Slice, TaggedEvent

if TYPE_CHECKING:
    from collections.abc import Sequence


TDecision = TypeVar("TDecision", bound=AbstractDecision)
TSlice = TypeVar("TSlice", bound=Slice[Any])


def selector_matches(
    selector: Selector[AbstractDecision],
    event: TaggedEvent[AbstractDecision],
) -> bool:
    """
    Implements DCB selection semantics for a single Selector.

    - Types are ORed.
    - Tags are ANDed.
    """

    type_matches = not selector.types or type(event.decision) in selector.types

    tag_matches = not selector.tags or set(selector.tags).issubset(event.tags)

    return type_matches and tag_matches


def boundary_matches(
    boundary: Selector[AbstractDecision] | Sequence[Selector[AbstractDecision]],
    event: TaggedEvent[AbstractDecision],
) -> bool:
    """
    Implements DCB selection semantics for a consistency boundary.

    Multiple selectors are ORed.
    """

    selectors = [boundary] if isinstance(boundary, Selector) else boundary

    return any(selector_matches(selector, event) for selector in selectors)


class Then(Generic[TSlice]):
    def __init__(
        self,
        expected: Sequence[TaggedEvent[AbstractDecision]],
        collected: Sequence[TaggedEvent[AbstractDecision]],
        slice_: TSlice,
    ):
        self.expected = list(expected)
        self.collected = list(collected)
        self.slice = slice_
        assert len(self.collected) == len(
            self.expected
        ), f"Expected {len(self.expected)} events, got {len(self.collected)}"
        for i, (actual, exp) in enumerate(
            zip(self.collected, self.expected, strict=True)
        ):
            assert actual.decision == exp.decision, (
                f"Event {i} decision mismatch: "
                f"expected {exp.decision}, got {actual.decision}"
            )
            assert (
                actual.tags == exp.tags
            ), f"Event {i} tags mismatch: expected {exp.tags}, got {actual.tags}"


class When(Generic[TSlice]):
    def __init__(
        self,
        given_events: Sequence[TaggedEvent[AbstractDecision]],
        slice_: TSlice,
    ):
        self.given_events = list(given_events)
        self.slice = slice_
        boundary = self.slice.consistency_boundary()

        for event in self.given_events:
            if not boundary_matches(boundary, event):
                msg = f"Consistency boundary wouldn't have selected: {event}"
                raise AssertionError(msg)

        for event in self.given_events:
            event.mutate(self.slice)

        self.slice.execute()
        self.collected = list(self.slice.collect_events())

    def then(
        self,
        *expected: TaggedEvent[AbstractDecision],
    ) -> TSlice:
        return Then(expected, self.collected, self.slice).slice


class Given:
    def __init__(
        self,
        *events: TaggedEvent[AbstractDecision],
    ):
        self.events = list(events)

    def when(self, slice_: TSlice, /) -> When[TSlice]:
        return When(
            given_events=self.events,
            slice_=slice_,
        )


class WhenSlice(Generic[TSlice]):
    def __init__(self, slice_: TSlice):
        self.slice = slice_

    def given(
        self,
        *events: TaggedEvent[AbstractDecision],
    ) -> When[TSlice]:
        return When(
            given_events=list(events),
            slice_=self.slice,
        )


def given(
    *events: TaggedEvent[AbstractDecision],
) -> Given:
    return Given(*events)


def when(slice_: TSlice, /) -> WhenSlice[TSlice]:
    return WhenSlice(slice_)
