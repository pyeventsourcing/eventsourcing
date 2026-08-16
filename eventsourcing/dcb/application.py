from __future__ import annotations

import contextlib
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar, override
from typing_extensions import deprecated


from eventsourcing.application import (
    AbstractApplicationSubscription,
    BoundedContext,
    SupportsApplicationSubscriptions,
)
from eventsourcing.dcb.api import DcbQuery, DcbQueryItem
from eventsourcing.dcb.persistence import (
    DcbEventStore,
    DcbInfrastructureFactory,
    NotFoundError,
)
from eventsourcing.domain import (
    EnduringObject,
    Group,
    Perspective,
    Selector,
    Slice,
)
from eventsourcing.metadata import null_metadata_in_context
from eventsourcing.persistence import (
    TaggedEventMapper,
    Tracking,
    Transcoder,
)
from eventsourcing.types import StateMutatorProtocol, TaggedEventProtocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType
    from typing import Self

    from eventsourcing.utils import EnvType


class DcbApplicationSubscription[TDecision](
    AbstractApplicationSubscription[TaggedEventProtocol[TDecision]]
):
    """An iterator that yields all events recorded in an application
    sequence that have sequence numbers greater than a given value. The iterator
    will block when all events have been yielded, and then
    continue when new ones are recorded. Events are returned along
    with tracking objects that identify the position in the application sequence.
    """

    def __init__(
        self,
        app: DcbApplication[TDecision],
        gt: int | None = None,
        topics: Sequence[str] = (),
    ):
        """
        Starts a subscription to application's recorder.
        """
        self.name = app.context_name
        self.recorder = app.recorder
        self.mapper = app.mapper
        self.subscription = self.recorder.subscribe(
            query=DcbQuery(items=[DcbQueryItem(types=list(topics))]),
            after=gt,
        )

    @override
    def stop(self) -> None:
        """Stops the subscription to the application's recorder."""
        self.subscription.stop()

    @override
    def __enter__(self) -> Self:
        """Calls __enter__ on the stored event subscription."""
        self.subscription.__enter__()
        return self

    @override
    def __exit__(self, *args: object, **kwargs: Any) -> None:
        """Calls __exit__ on the stored event subscription."""
        self.subscription.__exit__(*args, **kwargs)

    @override
    def __iter__(self) -> Self:
        return self

    @override
    def __next__(
        self,
    ) -> tuple[TaggedEventProtocol[TDecision], Tracking]:
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


class BasicDcbApplication(
    BoundedContext,
):
    env: ClassVar[dict[str, str]] = {"PERSISTENCE_MODULE": "eventsourcing.dcb.popo"}

    def __init__(self, *, env: EnvType | None = None, context_name: str | None = None):
        super().__init__(env=env, context_name=context_name)
        self.factory = DcbInfrastructureFactory.construct(self.env)
        self.recorder = self.factory.dcb_recorder()


class DcbApplication[TDecision](
    BasicDcbApplication,
    SupportsApplicationSubscriptions[
        TDecision,
        DcbApplicationSubscription[TDecision],
    ],
):
    def __init__(self, *, env: EnvType | None = None, context_name: str | None = None):
        super().__init__(env=env, context_name=context_name)
        transcoder = self.construct_transcoder()
        self.mapper = TaggedEventMapper[TDecision](
            transcoder=transcoder,
            compressor=self.factory.compressor(),
            cipher=self.factory.cipher(),
        )
        self.events = DcbEventStore[TDecision](self.mapper, self.recorder)
        self.repository = DcbRepository[TDecision](self.events)

    def construct_transcoder(self) -> Transcoder[TDecision]:
        return self.factory.transcoder()

    @deprecated("Use execute() for commands and evaluate() for queries")
    def do[TSlice: Slice[Any]](self, s: TSlice) -> TSlice:
        """
        Advances and executes a slice, then saves new decisions.
        """
        if type(s).do_projection:
            s = self.repository.advance(s)
        s.execute()
        if s.new_decisions:
            self.repository.save(s)
        return s

    def execute(self, s: Slice[TDecision]) -> int | None:
        """
        Advances and executes slice, saves events, returns sequence position.
        """
        if s.do_projection:
            s = self.repository.advance(s)
        s.execute()
        if s.new_decisions:
            return self.repository.save(s)
        return None

    def evaluate[TSlice: Slice[Any]](self, s: TSlice) -> TSlice:
        """
        Advances and return slice.
        """
        return self.repository.advance(s)

    @override
    def application_subscription(
        self,
        gt: int | None = None,
        topics: Sequence[str] = (),
    ) -> DcbApplicationSubscription[TDecision]:
        return DcbApplicationSubscription(
            app=self,
            gt=gt,
            topics=topics,
        )

    @override
    def close(self) -> None:
        self.factory.close()

    @override
    def __enter__(self) -> Self:
        return self

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


class DcbRepository[TDecision]:
    def __init__(self, eventstore: DcbEventStore[TDecision]):
        self.eventstore = eventstore

    def save(self, p: Perspective[TDecision]) -> int:
        return self.eventstore.append(
            events=p.collect_events(),
            cb=p.consistency_boundary(),
            after=p.last_known_position,
        )

    def get[TState: EnduringObject[Any]](
        self, enduring_object_id: str, enduring_object_cls: type[TState]
    ) -> TState:
        cb = [Selector[TDecision](tags=[enduring_object_id])]
        events = self.eventstore.read(*cb)
        new_obj: TState = enduring_object_cls.__new__(enduring_object_cls)
        new_obj.id = enduring_object_id
        count_events = 0
        obj: TState | None = new_obj
        for event in events:
            assert isinstance(event, StateMutatorProtocol)
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
            new_obj = obj_cls.__new__(  # pyrefly: ignore [bad-argument-count, bad-specialization]
                obj_cls
            )
            new_obj.id = obj_id
            objs[obj_id] = new_obj
        event_counts: dict[str, int] = defaultdict(int)
        read_response = self.eventstore.read(cb)
        for event in read_response:
            assert isinstance(event, StateMutatorProtocol)
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

    def get_group[TState: Group[Any]](
        self, cls: type[TState], *enduring_object_ids: str
    ) -> TState:
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

    def advance[TState: Perspective[Any]](self, p: TState) -> TState:
        read_response = self.eventstore.read(
            cb=p.consistency_boundary(),
            after=p.last_known_position,
        )
        for event in read_response:
            assert isinstance(event, StateMutatorProtocol)
            event.mutate(p)
        p.last_known_position = read_response.head
        return p
