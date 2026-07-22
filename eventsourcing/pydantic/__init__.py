from abc import ABC

import eventsourcing.domain
from eventsourcing.pydantic import application, immutable, mutable, transcoder


class Decision(immutable.PydanticDecision):
    pass  # pragma: no cover


class Aggregate(mutable.PydanticAggregate[Decision]):
    pass  # pragma: no cover


class AggregateState(mutable.PydanticAggregateState):
    pass  # pragma: no cover


class AggregateSnapshot(mutable.PydanticAggregateSnapshot[Decision]):
    pass  # pragma: no cover


class AggregatesApplication(application.PydanticAggregatesApplication[Decision]):
    pass  # pragma: no cover


class DCBApplication(application.PydanticDCBApplication[Decision]):
    pass  # pragma: no cover


class EnduringObject(mutable.PydanticEnduringObject[Decision]):
    pass  # pragma: no cover


class Group(mutable.PydanticGroup[Decision]):
    pass  # pragma: no cover


class Immutable(immutable.PydanticImmutable):
    pass  # pragma: no cover


class ImmutableAggregate(immutable.PydanticImmutableAggregate):
    pass  # pragma: no cover


class ImmutableAggregateSnapshot(immutable.PydanticImmutableAggregateSnapshot):
    pass  # pragma: no cover


class Selector(eventsourcing.domain.Selector[Decision]):
    pass  # pragma: no cover


class Slice(mutable.PydanticSlice[Decision], ABC):
    pass  # pragma: no cover


class Transcoder(transcoder.PydanticTranscoder[Decision]):
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
