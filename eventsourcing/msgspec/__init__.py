import eventsourcing.domain
from eventsourcing.msgspec.application import (
    AggregatesApplication,
    DcbApplication,
    EventSourcedProjection,
    ProcessApplication,
)
from eventsourcing.msgspec.immutable import (
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
    StreamEvent,
    TaggedEvent,
)
from eventsourcing.msgspec.mutable import (
    Aggregate,
    AggregateState,
    CommandSlice,
    EnduringObject,
    Group,
    MuetableAggregateSnapshot,
    QuerySlice,
)
from eventsourcing.msgspec.transcoder import Transcoder


class Selector(eventsourcing.domain.Selector[Decision]):
    pass


__all__ = [
    "Aggregate",
    "AggregateState",
    "AggregatesApplication",
    "CommandSlice",
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
    "QuerySlice",
    "Selector",
    "StreamEvent",
    "TaggedEvent",
    "Transcoder",
]
