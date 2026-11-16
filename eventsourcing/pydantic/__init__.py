from dataclasses import dataclass

import eventsourcing.domain
from eventsourcing.pydantic.application import (
    AggregatesApplication,
    DcbApplication,
    EventSourcedProjection,
    ProcessApplication,
)
from eventsourcing.pydantic.immutable import (
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
    StreamEvent,
    TaggedEvent,
)
from eventsourcing.pydantic.mutable import (
    Aggregate,
    AggregateState,
    CommandSlice,
    EnduringObject,
    Group,
    MutableAggregateSnapshot,
    QuerySlice,
)
from eventsourcing.pydantic.transcoder import Transcoder


@dataclass
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
    "MutableAggregateSnapshot",
    "ProcessApplication",
    "QuerySlice",
    "Selector",
    "StreamEvent",
    "TaggedEvent",
    "Transcoder",
]
