import eventsourcing.domain
from eventsourcing.msgspec.application import (
    AggregatesApplication,
    DcbApplication,
    ProcessApplication,
)
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
    "DcbApplication",
    "Decision",
    "EnduringObject",
    "Group",
    "Immutable",
    "ImmutableAggregate",
    "ImmutableAggregateSnapshot",
    "ProcessApplication",
    "Selector",
    "Slice",
    "Transcoder",
]
