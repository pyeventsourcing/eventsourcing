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
import eventsourcing.domain
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

    # TODO: Maybe check this when instantiating?
    # def __init_subclass__(cls, **kwargs: Any) -> None:
    #     super().__init_subclass__(**kwargs)
    #     type_of_snapshot_state = typing.get_type_hints(cls)["state"]
    #     try:
    #         assert issubclass(
    #             type_of_snapshot_state, SnapshotState
    #         ), type_of_snapshot_state
    #     except (TypeError, AssertionError) as e:
    #         msg = (
    #             f"Subclass of {SnapshotState}"
    #             f" is required as the annotated type of 'state' on "
    #             f"{cls}, got: {type_of_snapshot_state}"
    #         )
    #         raise TypeError(msg) from e


class AggregateSnapshotUuidID(AggregateSnapshot[UUID]):
    pass


class AggregateSnapshotStrID(AggregateSnapshot[str]):
    pass


class Aggregate(BaseAggregate):
    @staticmethod
    def create_id(*_: Any, **__: Any) -> UUID:
        """Returns a new aggregate ID."""
        return uuid4()

    class Event(DomainEvent, CanMutateAggregate):
        pass

    class Created(Event, CanInitAggregate):
        originator_topic: str

class GenericAggregate(BaseAggregate[TAggregateID]):
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

    class Created(Event, CanInitAggregate[TAggregateID]):
        originator_topic: str

    class Snapshot(AggregateSnapshot[TAggregateID]):
        pass


class AggregateUuidID(BaseAggregate[UUID]):
    @staticmethod
    def create_id(*_: Any, **__: Any) -> UUID:
        """Returns a new aggregate ID."""
        return uuid4()

    class Event(DomainEvent[UUID], CanMutateAggregate[UUID]):
        pass

    class Created(Event, CanInitAggregate[UUID]):
        originator_topic: str


class AggregateStrID(BaseAggregate[str]):
    @classmethod
    def create_id(cls, *_: Any, **__: Any) -> str:
        """Returns a new aggregate ID."""
        return f"{cls.__name__.lower()}-{uuid4()}"

    class Event(DomainEvent[str], CanMutateAggregate[str]):
        pass

    class Created(Event, CanInitAggregate[str]):
        originator_topic: str

    class Snapshot(Event, AggregateSnapshot[str]):
        pass
