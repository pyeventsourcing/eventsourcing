from abc import ABC

import eventsourcing.domain
from eventsourcing.msgspec import application, immutable, mutable, transcoder


class Decision(immutable.MsgspecDecision):
    pass  # pragma: no cover


class Aggregate(mutable.MsgspecAggregate[Decision]):
    pass  # pragma: no cover


class AggregateSnapshot(mutable.MsgspecAggregateSnapshot[Decision]):
    pass  # pragma: no cover


class AggregateState(mutable.MsgspecAggregateState):
    pass  # pragma: no cover


class AggregatesApplication(application.MsgspecAggregatesApplication[Decision]):
    pass  # pragma: no cover


class DCBApplication(application.MsgspecDCBApplication[Decision]):
    pass  # pragma: no cover


class EnduringObject(mutable.MsgspecEnduringObject[Decision]):
    pass  # pragma: no cover


class Group(mutable.MsgspecGroup[Decision]):
    pass  # pragma: no cover


class Immutable(immutable.MsgspecImmutable):
    pass  # pragma: no cover


class ImmutableAggregate(immutable.MsgspecImmutableAggregate):
    pass  # pragma: no cover


class ImmutableAggregateSnapshot(immutable.MsgspecImmutableAggregateSnapshot):
    pass  # pragma: no cover


class Selector(eventsourcing.domain.Selector[Decision]):
    pass  # pragma: no cover


class Slice(mutable.MsgspecSlice[Decision], ABC):
    pass  # pragma: no cover


class Transcoder(transcoder.MsgspecTranscoder[Decision]):
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
    "Selector",
    "Slice",
    "Transcoder",
]
