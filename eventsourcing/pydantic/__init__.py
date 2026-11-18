from dataclasses import dataclass

import eventsourcing.domain
from eventsourcing.pydantic.application import (
    AggregatesApplication,
    AggregatesApplicationPolicy,
    DcbApplication,
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
