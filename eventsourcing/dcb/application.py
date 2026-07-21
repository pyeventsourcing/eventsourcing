from __future__ import annotations

import os
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Generic

from typing_extensions import TypeVar

from eventsourcing.dcb.persistence import (
    DCBEventStore,
    DCBInfrastructureFactory,
    NotFoundError,
)
from eventsourcing.domain import (
    EnduringObject,
    Perspective,
    Selector,
    TDecision,
    TGroup,
    TPerspective,
    TSlice,
)
from eventsourcing.persistence import TaggedEventMapper, TrackingRecorder, Transcoder
from eventsourcing.utils import Environment, EnvType

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType
    from typing import Self


class DCBApplication(Generic[TDecision]):
    name = "DCBApplication"
    env: Mapping[str, str] = {"PERSISTENCE_MODULE": "eventsourcing.dcb.popo"}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if "name" not in cls.__dict__:
            cls.name = cls.__name__

    def __init__(self, env: EnvType | None = None):
        env_ = self.construct_env(self.name, env)
        self.env = env_
        self.factory: DCBInfrastructureFactory[TrackingRecorder] = (
            DCBInfrastructureFactory.construct(env_)
        )

        self.recorder = self.factory.dcb_recorder()
        transcoder = self.construct_transcoder()
        if transcoder is not None:
            # Only need a mapper, event store, and repository
            # if we are using the higher-level abstractions.
            self.mapper = TaggedEventMapper[TDecision](
                transcoder=transcoder,
                compressor=self.factory.compressor(),
                cipher=self.factory.cipher(),
            )
            self.events = DCBEventStore[TDecision](self.mapper, self.recorder)
            self.repository = DCBRepository[TDecision](self.events)

    def construct_transcoder(self) -> Transcoder[TDecision] | None:
        return self.factory.transcoder() if "TRANSCODER_TOPIC" in self.env else None

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


TEnduringObject = TypeVar("TEnduringObject", bound=EnduringObject[Any])


class DCBRepository(Generic[TDecision]):
    def __init__(self, eventstore: DCBEventStore[TDecision]):
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
        cb = [Selector[TDecision](tags=[enduring_object_id])]
        events = self.eventstore.read(*cb)
        new_obj: TEnduringObject = enduring_object_cls.__new__(enduring_object_cls)
        new_obj.id = enduring_object_id
        count_events = 0
        obj: TEnduringObject | None = new_obj
        for event in events:
            count_events += 1
            obj = event.mutate(obj)
        if count_events == 0 or obj is None:
            raise NotFoundError
        obj.last_known_position = events.head
        return obj

    def get_many(
        self,
        ids: Sequence[str],
        *,
        classes: Sequence[type[EnduringObject[TDecision]]] = (),
        cls: type[EnduringObject[TDecision]] | None = None,
    ) -> list[EnduringObject[TDecision] | None]:
        if len(classes) == 0:
            assert cls is not None
            classes = [cls] * len(ids)
        cb = [Selector[TDecision](tags=[id_]) for id_ in ids]
        objs: dict[str, EnduringObject[TDecision] | None] = {}
        for obj_id, obj_cls in zip(ids, classes, strict=True):
            new_obj = cls.__new__(obj_cls)
            new_obj.id = obj_id
            objs[obj_id] = new_obj
        event_counts: dict[str, int] = defaultdict(int)
        read_response = self.eventstore.read(cb)
        for event in read_response:
            for tag in event.tags:
                event_counts[tag] += 1
                obj = objs.get(tag)
                if obj is not None:
                    objs[tag] = event.mutate(obj)
        for id_ in ids:
            obj = objs.get(id_)
            if event_counts[id_] == 0 or obj is None:
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
        read_response = self.eventstore.read(
            cb=p.consistency_boundary(),
            after=p.last_known_position,
        )
        for event in read_response:
            event.mutate(p)
        p.last_known_position = read_response.head
        return p
