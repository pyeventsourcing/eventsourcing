from abc import ABC

from eventsourcing.dataclasses import application, immutable, mutable, transcoder


class Decision(immutable.DataclassDecision):
    pass  # pragma: no cover


class Aggregate(mutable.DataclassAggregate[Decision]):
    pass  # pragma: no cover


class AggregateState(mutable.DataclassAggregateState):
    pass  # pragma: no cover


class AggregateSnapshot(mutable.DataclassAggregateSnapshot[Decision]):
    pass  # pragma: no cover


class AggregatesApplication(application.DataclassAggregatesApplication[Decision]):
    pass  # pragma: no cover


class DCBApplication(application.DataclassDCBApplication[Decision]):
    pass  # pragma: no cover


class EnduringObject(mutable.DataclassEnduringObject[Decision]):
    pass  # pragma: no cover


class Group(mutable.DataclassGroup[Decision]):
    pass  # pragma: no cover


class Immutable(immutable.DataclassImmutable):
    pass  # pragma: no cover


class ImmutableAggregate(immutable.DataclassImmutableAggregate):
    pass  # pragma: no cover


class ImmutableAggregateSnapshot(immutable.DataclassImmutableAggregateSnapshot):
    pass  # pragma: no cover


class Slice(mutable.DataclassSlice[Decision], ABC):
    pass  # pragma: no cover


class Transcoder(transcoder.DataclassTranscoder[Decision]):
    pass  # pragma: no cover


__all__ = [
    "Aggregate",
    "AggregateSnapshot",
    "AggregateState",
    "AggregatesApplication",
    "DCBApplication",
    "Decision",
    "EnduringObject",
    "Group",
    "Immutable",
    "ImmutableAggregate",
    "ImmutableAggregateSnapshot",
    "Slice",
    "Transcoder",
]
