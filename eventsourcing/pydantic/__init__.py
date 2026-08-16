from dataclasses import dataclass

import eventsourcing.domain
from eventsourcing.pydantic.application import (
    AggregatesApplication,
    DcbApplication,
    ProcessApplication,
)
from eventsourcing.pydantic.immutable import (
    Decision,
    Immutable,
    ImmutableAggregate,
    ImmutableAggregateSnapshot,
)
from eventsourcing.pydantic.mutable import (
    Aggregate,
    AggregateSnapshot,
    AggregateState,
    EnduringObject,
    Group,
    Slice,
)
from eventsourcing.pydantic.transcoder import Transcoder


@dataclass
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
