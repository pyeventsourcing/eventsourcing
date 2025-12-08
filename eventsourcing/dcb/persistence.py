from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Generic

from eventsourcing.dcb.api import (
    DCBAppendCondition,
    DCBEvent,
    DCBQuery,
    DCBQueryItem,
    DCBReadResponse,
    DCBRecorder,
)
from eventsourcing.dcb.domain import (
    Selector,
    Tagged,
    TMutates,
)
from eventsourcing.persistence import InfrastructureFactory, TTrackingRecorder
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from collections.abc import Sequence


class DCBMapper(ABC, Generic[TMutates]):
    @abstractmethod
    def to_dcb_event(self, event: Tagged[TMutates]) -> DCBEvent:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def to_domain_event(self, event: DCBEvent) -> Tagged[TMutates]:
        raise NotImplementedError  # pragma: no cover


class DCBEventStore(Generic[TMutates]):
    def __init__(self, mapper: DCBMapper[TMutates], recorder: DCBRecorder):
        self.mapper = mapper
        self.recorder = recorder

    def put(
        self,
        events: Sequence[Tagged[TMutates]],
        cb: Selector | Sequence[Selector] | None = None,
        after: int | None = None,
    ) -> int:
        if not cb and not after:
            condition = None
        else:
            query = self._cb_to_dcb_query(cb)
            condition = DCBAppendCondition(
                fail_if_events_match=query,
                after=after,
            )
        return self.recorder.append(
            events=[self.mapper.to_dcb_event(e) for e in events],
            condition=condition,
        )

    def get(
        self,
        cb: Selector | Sequence[Selector] | None = None,
        *,
        after: int | None = None,
    ) -> DCBEventStoreGetResponse[TMutates]:
        query = self._cb_to_dcb_query(cb)
        read_response = self.recorder.read(
            query=query,
            after=after,
        )
        return DCBEventStoreGetResponse(read_response, self.mapper)

    @staticmethod
    def _cb_to_dcb_query(
        cb: Selector | Sequence[Selector] | None = None,
    ) -> DCBQuery:
        cb = [cb] if isinstance(cb, Selector) else cb or []
        return DCBQuery(
            items=[
                DCBQueryItem(
                    types=[get_topic(t) for t in s.types],
                    tags=list(s.tags),
                )
                for s in cb
            ]
        )


class DCBEventStoreGetResponse(Iterator[Tagged[TMutates]]):
    def __init__(self, dcb_read_response: DCBReadResponse, mapper: DCBMapper[TMutates]):
        self._dcb_read_response = dcb_read_response
        self._mapper = mapper

    @property
    def head(self) -> int | None:
        return self._dcb_read_response.head

    def __next__(self) -> Tagged[TMutates]:
        dcb_sequenced_event = self._dcb_read_response.__next__()
        return self._mapper.to_domain_event(dcb_sequenced_event.event)


class NotFoundError(Exception):
    pass


class DCBInfrastructureFactory(InfrastructureFactory[TTrackingRecorder], ABC):
    @abstractmethod
    def dcb_event_store(self) -> DCBRecorder:
        pass  # pragma: no cover
