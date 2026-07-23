import eventsourcing.domain
from eventsourcing.dataclasses.application import AggregatesApplication, DCBApplication
from eventsourcing.dataclasses.immutable import (
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
)
from eventsourcing.dataclasses.mutable import (
    Aggregate,
    AggregateSnapshot,
    AggregateState,
    EnduringObject,
    Group,
    Slice,
)
from eventsourcing.dataclasses.transcoder import Transcoder


class Selector(eventsourcing.domain.Selector[Decision]):
    pass


__all__ = [
    "Aggregate",
    "AggregateSnapshot",
    "AggregateState",
    "AggregatesApplication",
    "DCBApplication",
    "Decision",
    "EnduringObject",
    "Group",
    "Immutable",
    "ImmutableAggregate",
    "ImmutableAggregateSnapshot",
    "Selector",
    "Slice",
    "Transcoder",
]
