from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import ConfigDict, TypeAdapter

from eventsourcing.domain import (
    BaseAggregate,
    CanInitAggregate,
    CanMutateAggregate,
    CanSnapshotAggregate,
    TAggregateID,
)
from eventsourcing.pydantic.immutablemodel import DomainEvent, Immutable
from eventsourcing.utils import unwrap_new_type

datetime_adapter = TypeAdapter(datetime)


class SnapshotState(Immutable):
    model_config = ConfigDict(extra="allow")

    def __init__(self, **kwargs: Any) -> None:
        for key in ["_created_on", "_modified_on"]:
            kwargs[key] = datetime_adapter.validate_python(kwargs[key])
        super().__init__(**kwargs)


class AggregateSnapshot(DomainEvent[TAggregateID], CanSnapshotAggregate[TAggregateID]):
    topic: str
    state: Any


class Aggregate(BaseAggregate[TAggregateID]):
    @classmethod
    def create_id(cls, *_: Any, **__: Any) -> TAggregateID:
        """Returns a new aggregate ID."""
        assert cls.originator_id_type is not None
        new_id = uuid4()
        if issubclass(unwrap_new_type(cls.originator_id_type), UUID):
            return cast(TAggregateID, new_id)
        if issubclass(unwrap_new_type(cls.originator_id_type), str):
            return cast(TAggregateID, str(new_id))
        msg = f"The originator_id_type of {cls} apparently isn't a UUID or str"
        raise TypeError(msg)

    class Event(DomainEvent[TAggregateID], CanMutateAggregate[TAggregateID]):
        pass

    class Created(Event[TAggregateID], CanInitAggregate[TAggregateID]):
        originator_topic: str

    # # TODO: Why does Pydantic says GenericAggregate.Snapshot is not generic?
    # class Snapshot(AggregateSnapshot[TAggregateID):
