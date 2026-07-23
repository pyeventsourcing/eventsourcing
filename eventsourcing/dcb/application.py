from __future__ import annotations

import contextlib
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from eventsourcing.application import (
    AbstractApplication,
    AbstractApplicationSubscription,
)
from eventsourcing.dcb.api import DCBQuery, DCBQueryItem
from eventsourcing.dcb.persistence import (
    DCBEventStore,
    DCBInfrastructureFactory,
    NotFoundError,
)
from eventsourcing.domain import (
    EnduringObject,
    Perspective,
    Selector,
    TaggedEvent,
    TDecision,
    TGroup,
    TPerspective,
    TSlice,
    null_metadata_in_context,
)
from eventsourcing.persistence import (
    TaggedEventMapper,
    Tracking,
    TrackingRecorder,
    Transcoder,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType
    from typing import Self

    from eventsourcing.utils import EnvType


class DCBApplicationSubscription(
    AbstractApplicationSubscription[TaggedEvent[TDecision]]
):
    """An iterator that yields all events recorded in an application
    sequence that have sequence numbers greater than a given value. The iterator
    will block when all events have been yielded, and then
    continue when new ones are recorded. Events are returned along
    with tracking objects that identify the position in the application sequence.
    """

    def __init__(
        self,
        app: DCBApplication[TDecision],
        gt: int | None = None,
        topics: Sequence[str] = (),
    ):
        """
        Starts a subscription to application's recorder.
        """
        self.name = app.name
        self.recorder = app.recorder
        self.mapper = app.mapper
        self.subscription = self.recorder.subscribe(
            query=DCBQuery(items=[DCBQueryItem(types=list(topics))]),
            after=gt,
        )

    def stop(self) -> None:
        """Stops the subscription to the application's recorder."""
        self.subscription.stop()

    def __enter__(self) -> Self:
        """Calls __enter__ on the stored event subscription."""
        self.subscription.__enter__()
        return self

    def __exit__(self, *args: object, **kwargs: Any) -> None:
        """Calls __exit__ on the stored event subscription."""
        self.subscription.__exit__(*args, **kwargs)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> tuple[TaggedEvent[TDecision], Tracking]:
        """Returns the next stored event from subscription to the application's
        recorder. Constructs a tracking object that identifies the position of
        the event in the application sequence. Constructs a domain event object
        from the stored event object using the application's mapper. Returns a
        tuple of the domain event object and the tracking object.
        """
        sequenced = next(self.subscription)
        tracking = Tracking(self.name, sequenced.position)
        with null_metadata_in_context():
            event = self.mapper.to_tagged_event(sequenced.event)
        return event, tracking

    def __del__(self) -> None:
        """Stops the stored event subscription."""
        # Seems this doesn't get called with Python 3.13, hence 'no cover':
        with contextlib.suppress(AttributeError):  # pragma: no cover
            self.stop()


class DCBApplication(
    AbstractApplication[TDecision, DCBApplicationSubscription[TDecision]],
):
    env: ClassVar[dict[str, str]] = {"PERSISTENCE_MODULE": "eventsourcing.dcb.popo"}

    def __init__(self, env: EnvType | None = None):
        super().__init__(env=env)
        self.factory: DCBInfrastructureFactory[TrackingRecorder] = (
            DCBInfrastructureFactory.construct(self.env)
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

    def application_subscription(
        self,
        gt: int | None = None,
        topics: Sequence[str] = (),
    ) -> DCBApplicationSubscription[TDecision]:
        return DCBApplicationSubscription(
            app=self,
            gt=gt,
            topics=topics,
        )

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
            new_obj = obj_cls.__new__(obj_cls)
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
