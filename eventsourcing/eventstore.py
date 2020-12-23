from typing import Generic, Iterator, Optional
from uuid import UUID

from eventsourcing.recorders import AggregateRecorder
from eventsourcing.domainevent import TDomainEvent
from eventsourcing.eventmapper import Mapper


class EventStore(Generic[TDomainEvent]):
    """
    Stores and retrieves domain events.
    """

    def __init__(
        self,
        mapper: Mapper[TDomainEvent],
        recorder: AggregateRecorder,
    ):
        self.mapper = mapper
        self.recorder = recorder

    def put(self, events, **kwargs):
        """
        Stores domain events in aggregate sequence.
        """
        self.recorder.insert_events(
            list(
                map(
                    self.mapper.from_domain_event,
                    events,
                )
            ),
            **kwargs,
        )

    def get(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> Iterator[TDomainEvent]:
        """
        Retrieves domain events from aggregate sequence.
        """
        return map(
            self.mapper.to_domain_event,
            self.recorder.select_events(
                originator_id=originator_id,
                gt=gt,
                lte=lte,
                desc=desc,
                limit=limit,
            ),
        )
