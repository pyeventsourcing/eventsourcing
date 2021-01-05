from typing import List, Optional, Union
from uuid import UUID

from eventsourcing.domain import Aggregate
from eventsourcing.eventstore import EventStore
from eventsourcing.snapshotting import Snapshot


class AggregateNotFoundError(Exception):
    pass


class Repository:
    def __init__(
        self,
        event_store: EventStore[Aggregate.Event],
        snapshot_store: Optional[
            EventStore[Snapshot]
        ] = None,
    ):
        self.event_store = event_store
        self.snapshot_store = snapshot_store

    def get(
        self, aggregate_id: UUID, at: int = None
    ) -> Aggregate:

        gt = None
        domain_events: List[
            Union[Snapshot, Aggregate.Event]
        ] = []

        # Try to get a snapshot.
        if self.snapshot_store is not None:
            snapshots = self.snapshot_store.get(
                originator_id=aggregate_id,
                desc=True,
                limit=1,
                lte=at,
            )
            try:
                snapshot = next(snapshots)
                gt = snapshot.originator_version
                domain_events.append(snapshot)
            except StopIteration:
                pass

        # Get the domain events.
        domain_events += self.event_store.get(
            originator_id=aggregate_id,
            gt=gt,
            lte=at,
        )

        # Project the domain events.
        aggregate = None
        for domain_event in domain_events:
            aggregate = domain_event.mutate(aggregate)

        # Raise exception if not found.
        if aggregate is None:
            raise AggregateNotFoundError((aggregate_id, at))

        # Return the aggregate.
        assert isinstance(aggregate, Aggregate)
        return aggregate
