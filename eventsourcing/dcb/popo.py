from __future__ import annotations

import contextlib
from copy import deepcopy
from typing import TYPE_CHECKING, override

from eventsourcing.dcb.api import (
    DcbAppendCondition,
    DcbEvent,
    DcbQuery,
    DcbReadResponse,
    DcbRecorder,
    DcbSequencedEvent,
)
from eventsourcing.dcb.persistence import (
    DcbInfrastructureFactory,
    DcbListenNotifySubscription,
)
from eventsourcing.errors import ProgrammingError
from eventsourcing.persistence import IntegrityError
from eventsourcing.popo import POPOFactory, POPORecorder

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from threading import Event


class InMemoryDcbRecorder(DcbRecorder, POPORecorder):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[DcbSequencedEvent] = []
        self.position_sequence = self._position_sequence_generator()
        self._listeners: set[Event] = set()

    @override
    def head(self) -> int | None:
        with self._database_lock:
            return self.events[-1].position if self.events else None

    @override
    def read(
        self,
        query: DcbQuery | None = None,
        *,
        after: int | None = None,
        limit: int | None = None,
    ) -> DcbReadResponse:
        query = query or DcbQuery()
        with self._database_lock:
            events_generator = (
                event
                for event in self.events
                if (after is None or event.position > after)
                and (
                    not query.items
                    or any(
                        (not item.types or event.event.type in item.types)
                        and (set(event.event.tags) >= set(item.tags))
                        for item in query.items
                    )
                )
            )

            events = []
            for i, event in enumerate(events_generator):
                if limit is not None and i >= limit:
                    break
                events.append(deepcopy(event))
            if limit is None:
                head = self.events[-1].position if self.events else None
            else:
                head = events[-1].position if events else None
            # TODO: Change the previous few lines to actually be an iterator.
            return SimpleDcbReadResponse(iter(events), head)

    @override
    def append(
        self, events: Sequence[DcbEvent], condition: DcbAppendCondition | None = None
    ) -> int:
        if len(events) == 0:
            msg = "Should be at least one event. Avoid this elsewhere"
            raise ProgrammingError(msg)
        with self._database_lock:
            if condition is not None:
                read_response = self.read(
                    query=condition.fail_if_events_match,
                    after=condition.after,
                    limit=1,
                )
                try:
                    next(read_response)
                except StopIteration:
                    pass
                else:
                    raise IntegrityError(condition)
            self.events.extend(
                DcbSequencedEvent(
                    position=next(self.position_sequence),
                    event=deepcopy(event),
                )
                for event in events
            )
            self._notify_listeners()
            return self.events[-1].position

    def _position_sequence_generator(self) -> Iterator[int]:
        position = 1
        while True:
            yield position
            position += 1

    @override
    def subscribe(
        self,
        query: DcbQuery | None = None,
        *,
        after: int | None = None,
    ) -> InMemorySubscription:
        return InMemorySubscription(self, query=query, after=after)

    def listen(self, event: Event) -> None:
        self._listeners.add(event)

    def unlisten(self, event: Event) -> None:
        with contextlib.suppress(KeyError):
            self._listeners.remove(event)

    def _notify_listeners(self) -> None:
        for listener in self._listeners:
            listener.set()


class InMemorySubscription(DcbListenNotifySubscription[InMemoryDcbRecorder]):
    def __init__(
        self,
        recorder: InMemoryDcbRecorder,
        query: DcbQuery | None = None,
        after: int | None = None,
    ) -> None:
        super().__init__(recorder=recorder, query=query, after=after)
        self._recorder.listen(self._has_been_notified)

    @override
    def stop(self) -> None:
        super().stop()
        self._recorder.unlisten(self._has_been_notified)


class SimpleDcbReadResponse(DcbReadResponse):
    def __init__(self, events: Iterator[DcbSequencedEvent], head: int | None = None):
        self.events = events
        self._head_was_given = head is not None
        self._head = head

    @property
    @override
    def head(self) -> int | None:
        return self._head

    @override
    def __next__(self) -> DcbSequencedEvent:
        event = next(self.events)
        if not self._head_was_given:  # pragma: no cover
            self._head = event.position
        return event

    # def next_batch(self) -> list[DcbSequencedEvent]:
    #     """
    #     Returns a batch of events as a list.
    #     Updates the head position similar to __next__.
    #     """
    #     result = []
    #     max_batch_size = 100
    #
    #     # Get up to max_batch_size events from the iterator
    #     try:
    #         for _ in range(max_batch_size):
    #             event = next(self.events)
    #             if not self._head_was_given:
    #                 self._head = event.position
    #             result.append(event)
    #     except StopIteration:
    #         pass
    #     return result


class InMemoryDcbFactory(POPOFactory, DcbInfrastructureFactory):

    @override
    def dcb_recorder(self) -> DcbRecorder:
        return InMemoryDcbRecorder()

    @override
    def close(self) -> None:
        pass


del DcbInfrastructureFactory
