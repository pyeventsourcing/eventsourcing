import eventsourcing.domain
from eventsourcing.msgspec.application import (
    AggregatesApplication,
    DcbApplication,
    EventSourcedProjection,
    ProcessApplication,
)
from eventsourcing.msgspec.immutable import (
    AggregateEvent,
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
    TaggedEvent,
)
from eventsourcing.msgspec.mutable import (
    Aggregate,
    AggregateState,
    EnduringObject,
    Group,
    MuetableAggregateSnapshot,
    Slice,
)
from eventsourcing.msgspec.transcoder import Transcoder


class Selector(eventsourcing.domain.Selector[Decision]):
    pass


__all__ = [
    "Aggregate",
    "AggregateEvent",
    "AggregateState",
    "AggregatesApplication",
    "DcbApplication",
    "Decision",
    "EnduringObject",
    "EventSourcedProjection",
    "Group",
    "Immutable",
    "ImmutableAggregate",
    "ImmutableAggregateSnapshot",
    "MuetableAggregateSnapshot",
    "ProcessApplication",
    "Selector",
    "Slice",
    "TaggedEvent",
    "Transcoder",
]
