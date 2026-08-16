from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, override

from eventsourcing.errors import ProgrammingError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self
    from uuid import UUID


@dataclass
class DcbQueryItem:
    types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class DcbQuery:
    items: list[DcbQueryItem] = field(default_factory=list)


@dataclass
class DcbAppendCondition:
    fail_if_events_match: DcbQuery = field(default_factory=DcbQuery)
    after: int | None = None


@dataclass(kw_only=True)
class DcbEvent:
    type: str
    data: bytes
    tags: list[str] = field(default_factory=list)
    uuid: UUID
    metadata: dict[str, str]


@dataclass
class DcbSequencedEvent:
    event: DcbEvent
    position: int


class DcbReadResponse(Iterator[DcbSequencedEvent], ABC):
    @property
    @abstractmethod
    def head(self) -> int | None:
        pass  # pragma: no cover

    @abstractmethod
    @override
    def __next__(self) -> DcbSequencedEvent:
        pass  # pragma: no cover

    # @abstractmethod
    # def next_batch(self) -> list[DcbSequencedEvent]:
    #     """
    #     Returns a batch of events as a list.
    #     Updates the head position similar to __next__.
    #     """


class DcbRecorder(ABC):
    @abstractmethod
    def head(self) -> int | None:
        """
        Returns the highest integer sequence position in the database,
        or None if no events have been recorded.
        """

    @abstractmethod
    def read(
        self,
        query: DcbQuery | None = None,
        *,
        after: int | None = None,
        limit: int | None = None,
    ) -> DcbReadResponse:
        """
        Returns all events, unless 'after' is given then only those with position
        greater than 'after', and unless any query items are given, then only those
        that match at least one query item. An event matches a query item if its type
        is in the item types or there are no item types, and if all the item tags are
        in the event tags.
        """

    @abstractmethod
    def append(
        self, events: Sequence[DcbEvent], condition: DcbAppendCondition | None = None
    ) -> int:
        """
        Appends given events to the event store, unless the condition fails.
        """

    @abstractmethod
    def subscribe(
        self,
        query: DcbQuery | None = None,
        *,
        after: int | None = None,
    ) -> DcbSubscription[Self]:
        """
        Returns all events, unless 'after' is given then only those with position
        greater than 'after', and unless any query items are given, then only those
        that match at least one query item. An event matches a query item if its type
        is in the item types or there are no item types, and if all the item tags are
        in the event tags. The subscription will block when the last recorded event
        is received, and then continue when new events are recorded.
        """


class DcbSubscription[TDcbRecorder: DcbRecorder](Iterator[DcbSequencedEvent]):
    def __init__(
        self,
        recorder: TDcbRecorder,
        query: DcbQuery | None = None,
        after: int | None = None,
    ) -> None:
        self._recorder = recorder
        self._query = query
        self._has_been_entered = False
        self._has_been_stopped = False
        self._last_position: int = after or 0

    def __enter__(self) -> Self:
        if self._has_been_entered:
            msg = "Already entered subscription context manager"
            raise ProgrammingError(msg)
        self._has_been_entered = True
        return self

    def __exit__(self, *args: object, **kwargs: Any) -> None:
        if not self._has_been_entered:
            msg = "Not already entered subscription context manager"
            raise ProgrammingError(msg)
        self.stop()

    def stop(self) -> None:
        """Stops the subscription."""
        self._has_been_stopped = True

    @override
    def __iter__(self) -> Self:
        return self

    @abstractmethod
    @override
    def __next__(self) -> DcbSequencedEvent:
        """Returns the next DcbEvent in the sequence."""
