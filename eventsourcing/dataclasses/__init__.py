import eventsourcing.domain
from eventsourcing.dataclasses.application import (
    AggregatesApplication,
    DcbApplication,
    EventSourcedProjection,
    ProcessApplication,
)
from eventsourcing.dataclasses.immutable import (
    AggregateEvent,
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
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
    "AggregateEvent",
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
    "MutableAggregateSnapshot",
    "ProcessApplication",
    "QuerySlice",
    "Selector",
    "TaggedEvent",
    "Transcoder",
]
