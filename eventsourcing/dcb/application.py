from __future__ import annotations

import os
from collections import defaultdict
from typing import TYPE_CHECKING, Any, cast

from typing_extensions import TypeVar

from eventsourcing.dcb.domain import (
    EnduringObject,
    Perspective,
    Selector,
    TDecision,
    TGroup,
    TPerspective,
    TSlice,
)
from eventsourcing.dcb.persistence import (
    DCBEventStore,
    DCBInfrastructureFactory,
    DCBMapper,
    NotFoundError,
)
from eventsourcing.utils import Environment, EnvType, resolve_topic

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType
    from typing import Self


class DCBApplication:
    name = "DCBApplication"
    env: Mapping[str, str] = {"PERSISTENCE_MODULE": "eventsourcing.dcb.popo"}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if "name" not in cls.__dict__:
            cls.name = cls.__name__

    def __init__(self, env: EnvType | None = None):
        self.env = self.construct_env(self.name, env)
        self.factory = DCBInfrastructureFactory.construct(self.env)
        self.recorder = self.factory.dcb_recorder()
        if "MAPPER_TOPIC" in self.env:
            # Only need a mapper, event store, and repository
            # if we are using the higher-level abstractions.
            self.mapper = cast(DCBMapper, resolve_topic(self.env["MAPPER_TOPIC"])())
            assert isinstance(self.mapper, DCBMapper)
            self.events = DCBEventStore(self.mapper, self.recorder)
            self.repository = DCBRepository(self.events)

    def construct_env(self, name: str, env: EnvType | None = None) -> Environment:
        """Constructs environment from which application will be configured."""
        _env = dict(type(self).env)
        _env.update(os.environ)
        if env is not None:
            _env.update(env)
        return Environment(name, _env)

    def do(self, s: TSlice) -> TSlice:
        """
        Advances and executes a slice, then saves new decisions.
        """
        if type(s).do_projection:
            s = self.repository.advance(s)
        s.execute()
        if s.new_decisions:
            self.repository.save(s)
        return s

    def close(self) -> None:
        self.factory.close()

    def __enter__(self) -> Self:
        self.factory.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
        self.factory.__exit__(exc_type, exc_val, exc_tb)


TEnduringObject = TypeVar("TEnduringObject", bound=EnduringObject[Any, Any])


class DCBRepository:
    def __init__(self, eventstore: DCBEventStore):
        self.eventstore = eventstore

    def save(self, p: Perspective[TDecision]) -> int:
        return self.eventstore.append(
            events=p.collect_events(),
            cb=p.consistency_boundary(),
            after=p.last_known_position,
        )

    def get(
        self, enduring_object_id: str, enduring_object_cls: type[TEnduringObject]
    ) -> TEnduringObject:
        cb = [Selector(tags=[enduring_object_id])]
        events = self.eventstore.read(*cb)
        obj: TEnduringObject | None = enduring_object_cls.__new__(enduring_object_cls)
        count_events = 0
        for event in events:
            count_events += 1
            obj = event.decision.mutate(obj)
        if count_events == 0 or obj is None:
            raise NotFoundError
        obj.last_known_position = events.head
        return obj

    def get_many(
        self,
        ids: Sequence[str],
        *,
        classes: Sequence[type[EnduringObject[Any, Any]]] = (),
        cls: type[EnduringObject[Any, Any]] | None = None,
    ) -> list[EnduringObject[Any] | None]:
        if len(classes) == 0:
            assert cls is not None
            classes = [cls] * len(ids)
        cb = [Selector(tags=[id_]) for id_ in ids]
        objs: dict[str, EnduringObject[Any, Any] | None] = {
            id_: cls.__new__(cls) for (id_, cls) in zip(ids, classes, strict=True)
        }
        event_counts: dict[str, int] = defaultdict(int)
        read_response = self.eventstore.read(cb)
        for tagged in read_response:
            for tag in tagged.tags:
                event_counts[tag] += 1
                obj = objs.get(tag)
                if obj is not None:
                    objs[tag] = tagged.decision.mutate(obj)
        for id_ in ids:
            obj = objs.get(id_)
            if obj is None or event_counts[id_] == 0:
                objs[id_] = None
            else:
                obj.last_known_position = read_response.head
        return list(objs.values())

    def get_group(self, cls: type[TGroup], *enduring_object_ids: str) -> TGroup:
        enduring_objects = self.get_many(
            ids=enduring_object_ids,
            classes=cls.classes,
        )
        group = cls(*enduring_objects)
        last_known_positions = [
            o.last_known_position
            for o in enduring_objects
            if o and o.last_known_position
        ]
        group.last_known_position = (
            max(last_known_positions) if last_known_positions else None
        )
        return group

    def advance(self, p: TPerspective) -> TPerspective:
        events = self.eventstore.read(
            cb=p.consistency_boundary(),
            after=p.last_known_position,
        )
        for event in events:
            event.decision.mutate(p)
        p.last_known_position = events.head
        return p
