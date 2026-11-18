import eventsourcing.domain
from eventsourcing.dataclasses.application import (
    AggregatesApplication,
    AggregatesApplicationPolicy,
    DcbApplication,
    ProcessApplication,
)
from eventsourcing.dataclasses.immutable import (
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
    StreamEvent,
    TaggedEvent,
)
from eventsourcing.dataclasses.mutable import (
    Aggregate,
    AggregateState,
    CommandSlice,
    EnduringObject,
    Group,
    MutableAggregateSnapshot,
    QuerySlice,
)
from eventsourcing.dataclasses.transcoder import Transcoder


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
    "MutableAggregateSnapshot",
    "ProcessApplication",
    "QuerySlice",
    "Selector",
    "StreamEvent",
    "TaggedEvent",
    "Transcoder",
]
