from dataclasses import dataclass

import eventsourcing.domain
from eventsourcing.pydantic.application import (
    AggregatesApplication,
    DcbApplication,
    EventSourcedProjection,
    ProcessApplication,
)
from eventsourcing.pydantic.immutable import (
    AggregateEvent,
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
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
