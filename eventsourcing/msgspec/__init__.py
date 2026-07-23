import eventsourcing.domain
from eventsourcing.msgspec.application import AggregatesApplication, DCBApplication
from eventsourcing.msgspec.immutable import (
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
)
from eventsourcing.msgspec.mutable import (
    Aggregate,
    AggregateSnapshot,
    AggregateState,
    EnduringObject,
    Group,
    Slice,
)
from eventsourcing.msgspec.transcoder import Transcoder


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
