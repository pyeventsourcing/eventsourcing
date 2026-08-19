from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import NoneType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Self,
    cast,
    final,
    get_args,
    get_type_hints,
    override,
)
from uuid import UUID, uuid4

from eventsourcing.decorator import (
    CommandMethodDecorator,
    SupportsEventDecorator,
    coerce_args_to_kwargs,
    filter_kwargs_for_method_params,
    get_decorated_func,
)
from eventsourcing.errors import ProgrammingError
from eventsourcing.metadata import get_metadata_from_context, set_metadata_in_context
from eventsourcing.types import (
    AggregateEventProtocol,
    Evolver,
    MutableAggregateProtocol,
    Projector,
    SelectorProtocol,
    StateMutatorProtocol,
    TaggedEventProtocol,
    WorksWithDecisions,
)
from eventsourcing.utils import (
    to_snake_case,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from eventsourcing.persistence import EventStore


NIL_UUID = UUID("00000000-0000-0000-0000-000000000000")
NIL_UUID_STR = str(NIL_UUID)


class Decision(ABC):
    def mutate[TState](self, obj: TState | None) -> TState | None:
        assert obj is not None

        # Identify the function that was decorated.
        if decorated_func := get_decorated_func((type(obj), type(self))):
            # Select event attributes mentioned in function signature.
            self_dict = self.as_dict()
            kwargs = filter_kwargs_for_method_params(self_dict, decorated_func)

            # Call the original method with event attribute values.
            decorated_method = decorated_func.__get__(obj, type(obj))
            try:
                decorated_method(**kwargs)
            except TypeError as e:  # pragma: no cover
                # TODO: Write a test that does this...
                msg = (
                    f"Failed to apply {type(self).__qualname__} to "
                    f"{type(obj).__qualname__} with kwargs {kwargs}: {e}"
                )
                raise TypeError(msg) from e

        self.apply(obj)
        return obj

    @abstractmethod
    def as_dict(self) -> dict[str, Any]:
        pass  # pragma: no cover

    def apply(self, obj: Any) -> None:  # noqa: B027
        pass


@dataclass(kw_only=True, frozen=True)
class EventEnvelope[TDecision]:
    decision: TDecision
    uuid: UUID = field(default_factory=uuid4)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)

    def mutate[TState](self, obj: TState | None) -> TState | None:
        with set_metadata_in_context(self.metadata):
            return cast(StateMutatorProtocol, self.decision).mutate(obj)


@dataclass(kw_only=True, frozen=True)
class TaggedEvent[TDecision](EventEnvelope[TDecision]):
    tags: list[str]


@dataclass(kw_only=True, frozen=True)
class AggregateEvent[TDecision](EventEnvelope[TDecision]):
    originator_id: str
    originator_version: int

    @override
    def mutate[TState](self, obj: TState | None) -> TState | None:
        if obj is None:
            return super().mutate(obj)
        assert isinstance(obj, MutableAggregateProtocol)
        if obj.id == NIL_UUID_STR:
            # We received a shell, so initialise the `id` and `version`.
            obj.id = self.originator_id
            obj.version = self.originator_version

            # Apply the event to the aggregate.
            return super().mutate(obj)

        # Check this event belongs to this aggregate.
        assert self.originator_id == obj.id
        # Check this event is the next one for this aggregate.
        assert self.originator_version == obj.version + 1, (
            self.originator_version,
            obj.version,
        )
        # Apply the event to the aggregate (allow for exceptions to be raised
        # before mutating any values).
        obj = super().mutate(obj)

        # Increment the version number.
        if obj is not None:
            assert isinstance(obj, MutableAggregateProtocol)
            obj.version = self.originator_version

        return obj


class MetaCallTriggersEvent(ABCMeta):
    def __call__[T](cls: type[T], *args: Any, **kwargs: Any) -> T:
        if cls in _abstract_enduring_object_classes:
            # TODO: Adjust these error messages to say something like
            #   like "can't call class that does not have a
            #   decorated __init__ method"
            try:
                cls.__dict__["__init__"]
            except KeyError:
                msg = f"Class {cls} has no __init__ method"
                raise ProgrammingError(msg) from None
            msg = f"__init__ method on {cls} " f"is not decorated with @event decorator"
            raise ProgrammingError(msg) from None

        # TODO: For convenience, make this error out in the same way
        #  as it would if the arguments didn't match the __init__
        #  method and __init__was called directly, and verify the
        #  event's __init__ is valid when initialising the class,
        #  just like we do for event-sourced aggregates.

        # assert issubclass(cls, EnduringObject)

        return cls._create(*args, **kwargs)  # type: ignore[attr-defined]


class CallTriggersEvent[TDecision](
    SupportsEventDecorator[TDecision],
    metaclass=MetaCallTriggersEvent,
):

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Check a subclasse of EnduringObject has an __init__ method.
        try:
            init_method = cls.__dict__["__init__"]
        except KeyError:
            _abstract_enduring_object_classes.add(cls)
            return
        if not isinstance(init_method, CommandMethodDecorator):
            _abstract_enduring_object_classes.add(cls)
            return
        init_method.avoid_delegating_to_init_method = True

    @classmethod
    def _create(cls, *args: Any, **kwargs: Any) -> Self:
        raise NotImplementedError


_abstract_enduring_object_classes = set[type[Any]]()


class Perspective[
    TDecision,
](
    # PerspectiveProtocol[TaggedEventProtocol[TDecision], TDecision],
    WorksWithDecisions[TDecision],
    ABC,
):
    last_known_position: int | None
    new_decisions: list[TaggedEventProtocol[TDecision]]

    def __new__(cls, *_: Any, **__: Any) -> Self:
        self = super().__new__(cls)
        self.last_known_position = None
        self.new_decisions = []
        return self

    @abstractmethod
    def consistency_boundary(
        self,
    ) -> SelectorProtocol[TDecision] | Sequence[SelectorProtocol[TDecision]]:
        raise NotImplementedError  # pragma: no cover

    def trigger_event[**P](
        self,
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """
        Constructs new event and appends to list of uncommitted events.
        """
        self.check_decision_type(decision_cls)
        envelope = TaggedEvent(
            tags=list(tags),
            decision=decision_cls(*args, **kwargs),
        )
        envelope.mutate(self)
        self.new_decisions.append(envelope)

    def collect_events(
        self,
    ) -> Sequence[TaggedEventProtocol[TDecision]]:
        """
        Drains list of triggered events.
        """
        collected, self.new_decisions = (
            self.new_decisions,
            list[TaggedEventProtocol[TDecision]](),
        )
        return collected


class EnduringObject[
    TDecision,
](
    Perspective[TDecision],
    CallTriggersEvent[TDecision],
):
    id: str
    continuity_id_name: ClassVar[str]

    def __init_subclass__(
        cls,
        continuity_id_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        cls.continuity_id_name = (
            cls.__dict__.get("continuity_id_name", continuity_id_name)
            or to_snake_case(cls.__name__) + "_id"
        )
        assert cls.continuity_id_name.endswith("_id")

    @classmethod
    def create_id(cls, **_: Any) -> str:
        return f"{cls.continuity_id_name[:-3].replace('_', '-')}-{uuid4()!s}"

    @classmethod
    @override
    def _create(cls: type[Self], *args: Any, **kwargs: Any) -> Self:
        obj = cls.__new__(cls)
        init_kwargs = coerce_args_to_kwargs(obj.__init__, args, kwargs)  # type: ignore[misc]
        id_kwargs = filter_kwargs_for_method_params(init_kwargs, cls.create_id)
        obj.id = init_kwargs.get(cls.continuity_id_name) or cls.create_id(**id_kwargs)
        # Calling __init__ should trigger an event that
        # calls the original decorated __init__ method.
        obj.__init__(*args, **kwargs)  # type: ignore[misc]
        return obj

    @override
    def consistency_boundary(
        self,
    ) -> SelectorProtocol[TDecision]:
        return Selector(tags=[self.id])

    @override
    def trigger_event[**P](
        self,
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        if self.continuity_id_name not in kwargs:
            kwargs[self.continuity_id_name] = self.id
        super().trigger_event(decision_cls, [self.id, *tags], *args, **kwargs)


class Group[
    TDecision,
](
    Perspective[TDecision],
):
    _enduring_objects: list[EnduringObject[TDecision]]
    classes: ClassVar[Sequence[type[EnduringObject[Any]]]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # 1. Get all the type hints from the __init__ method
        hints = get_type_hints(cls.__init__)

        extracted_classes: list[type[EnduringObject[Any]]] = []

        for param_name, hint in hints.items():
            # Ignore the return type and 'self' (if it happens to be annotated)
            if param_name in ("return", "self"):
                continue

            # 2. Extract arguments from the Union
            # (e.g., Student | None becomes (Student, NoneType))
            args = get_args(hint)

            if args:
                # Filter out NoneType to just get the actual class
                extracted_classes.extend(arg for arg in args if arg is not NoneType)
            else:
                # If it wasn't a Union/Optional, just append the hint directly
                extracted_classes.append(hint)
        assert all(issubclass(cls, EnduringObject) for cls in extracted_classes)
        cls.classes = extracted_classes

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        self = super().__new__(cls, *args, **kwargs)
        self._enduring_objects = [a for a in args if isinstance(a, EnduringObject)]
        return self

    @override
    def consistency_boundary(
        self,
    ) -> SelectorProtocol[TDecision] | Sequence[SelectorProtocol[TDecision]]:
        return [o.consistency_boundary() for o in self._enduring_objects]

    @override
    def trigger_event[**P](
        self,
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        objs = self._enduring_objects
        tags = [o.id for o in objs] + list(tags)
        new_event = TaggedEvent(
            tags=tags,
            decision=decision_cls(*args, **kwargs),
        )
        for o in objs:
            new_event.mutate(o)
        self.new_decisions.append(new_event)


@dataclass
class Selector[TDecision](SelectorProtocol[TDecision]):
    types: Sequence[type[TDecision]] = ()
    tags: Sequence[str] = ()


class BaseSlice[TDecision](
    Perspective[TDecision],
    SupportsEventDecorator[TDecision],
    ABC,
):
    pass


class CommandSlice[TDecision](BaseSlice[TDecision], ABC):
    @abstractmethod
    def execute(self) -> None:
        pass


class QuerySlice[TDecision](BaseSlice[TDecision]):
    @final
    def execute(self) -> None:
        msg = "A query slice doesn't need to be executed"
        raise ProgrammingError(msg)


class Aggregate[
    TDecision,
](
    # MutableAggregateProtocol[AggregateEventProtocol[TDecision]],
    CallTriggersEvent[TDecision],
):
    id: str
    version: int
    INITIAL_VERSION = 1
    new_decisions: list[AggregateEvent[TDecision]]

    def __new__(cls, *_: Any, **__: Any) -> Self:
        self = super().__new__(cls)
        self.new_decisions = []
        self.id = NIL_UUID_STR
        self.version = cls.INITIAL_VERSION - 1
        return self

    def collect_events(
        self,
    ) -> Sequence[AggregateEvent[TDecision]]:
        """
        Drains list of triggered events.
        """
        collected, self.new_decisions = (
            self.new_decisions,
            list[AggregateEvent[TDecision]](),
        )
        return collected

    @classmethod
    @override
    def _create(cls, *args: Any, **kwargs: Any) -> Self:
        obj = cls.__new__(cls, *args, **kwargs)
        # create_id_kwargs = filter_kwargs_for_method_params(
        #     _coerce_args_to_kwargs(cls.create_id, args, kwargs),
        #     cls.create_id,
        # )
        create_id = getattr(cls, "create_id", lambda: str(uuid4()))
        create_id_kwargs = filter_kwargs_for_method_params(kwargs, create_id)
        obj.id = create_id(**create_id_kwargs)
        # Calling __init__ should trigger an event that
        # calls the original decorated __init__ method.
        obj.__init__(*args, **kwargs)  # type: ignore[misc]
        return obj

    @override
    def trigger_event[**P](
        self,
        decision_cls: Callable[P, TDecision],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """
        Constructs new event and appends to list of uncommitted events.
        """
        self.check_decision_type(decision_cls)
        envelope = AggregateEvent(
            decision=decision_cls(*args, **kwargs),
            originator_id=self.id,
            originator_version=self.version + 1,
        )
        # print(
        #     f"Triggered {envelope.originator_id} version {envelope.originator_version}
        #     "
        # )
        envelope.mutate(self)
        self.new_decisions.append(envelope)

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        raise NotImplementedError  # pragma: no cover


def projector[TState, TEvent](
    mutator: Evolver[TState, TEvent],
) -> Projector[TState, TEvent]:
    def projector_function(
        obj: TState | None, events: Iterable[TEvent]
    ) -> TState | None:
        for e in events:
            obj = mutator(obj, e)
        return obj

    return projector_function


@projector  # type: ignore[arg-type]
def evolve_aggregate[
    TState: MutableAggregateProtocol[Any],
](
    obj: TState | None,
    envelope: AggregateEvent[Any],
) -> TState | None:
    return envelope.mutate(obj)


class EventSourcedLog[TDecision, SDecision]:
    """Constructs a sequence of domain events, like an aggregate.
    But unlike an aggregate the events can be triggered
    and selected for use in an application without
    reconstructing a current state from all the events.

    This allows an indefinitely long sequence of events to be
    generated and used without the practical restrictions of
    projecting the events into a current state before they
    can be used, which is useful e.g. for logging and
    progressively discovering all the aggregate IDs of a
    particular type in an application.
    """

    def __init__(
        self,
        events: EventStore[TDecision],
        originator_id: str,
        event_cls: type[SDecision],
    ):
        # TODO: Change `EventStore` to subclass WorksWithDecisions, then
        #  assert that event_cls is a subclass of its decision class.
        self.events = events
        self.originator_id = originator_id
        self.event_cls = event_cls

    def trigger_event(
        self,
        next_originator_version: int | None = None,
        **kwargs: Any,
    ) -> AggregateEvent[TDecision]:
        """Constructs and returns a new log event."""
        return self._trigger_event(
            logged_cls=self.event_cls,
            next_originator_version=next_originator_version,
            **kwargs,
        )

    def _trigger_event(
        self,
        logged_cls: type[SDecision],
        next_originator_version: int | None = None,
        **kwargs: Any,
    ) -> AggregateEvent[TDecision]:
        """Constructs and returns a new log event."""
        if next_originator_version is None:
            last_logged = self.get_last()
            if last_logged is None:
                next_originator_version = Aggregate.INITIAL_VERSION
            else:
                next_originator_version = last_logged.originator_version + 1

        return AggregateEvent(
            originator_id=self.originator_id,
            originator_version=next_originator_version,
            decision=cast(TDecision, logged_cls(**kwargs)),
        )

    def get_first(self) -> AggregateEventProtocol[SDecision] | None:
        """Selects the first logged event."""
        try:
            return next(self.get(limit=1))
        except StopIteration:
            return None

    def get_last(self) -> AggregateEventProtocol[SDecision] | None:
        """Selects the last logged event."""
        try:
            return next(self.get(desc=True, limit=1))
        except StopIteration:
            return None

    def get(
        self,
        *,
        gt: int | None = None,
        lte: int | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> Iterator[AggregateEventProtocol[SDecision]]:
        """Selects a range of logged events with limit,
        with ascending or descending order.
        """
        return cast(
            Iterator[AggregateEventProtocol[SDecision]],
            self.events.get(
                originator_id=self.originator_id,
                gt=gt,
                lte=lte,
                desc=desc,
                limit=limit,
            ),
        )
