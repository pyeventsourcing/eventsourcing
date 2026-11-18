import eventsourcing.domain
from eventsourcing.msgspec.application import (
    AggregatesApplication,
    AggregatesApplicationPolicy,
    DcbApplication,
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
    "AggregatesApplicationPolicy",
    "CommandSlice",
    "DcbApplication",
    "Decision",
    "EnduringObject",
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
