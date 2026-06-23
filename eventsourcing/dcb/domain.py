from __future__ import annotations

import types
import typing
from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Generic, ParamSpec, Self
from uuid import uuid4

from typing_extensions import TypeVar

from eventsourcing.domain import (
    AbstractDecision,
    CallableType,
    CommandMethodDecorator,
    ProgrammingError,
    all_func_decorators,
    decorated_func_callers,
    filter_kwargs_for_method_params,
)
from eventsourcing.utils import construct_topic

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class Decision(AbstractDecision, ABC):
    metadata: dict[str, str]

    @abstractmethod
    def as_dict(self) -> dict[str, Any]:
        pass  # pragma: no cover

    def mutate(self, obj: TPerspective | None) -> TPerspective | None:
        assert obj is not None

        # Identify the function that was decorated.
        try:
            decorated_func = decorated_funcs[(type(obj), type(self))]
        except KeyError:
            pass
        else:
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

    def apply(self, obj: Any) -> None:
        pass


TDecision = TypeVar("TDecision", bound=Decision, default=Decision)
"""
A type variable representing any subclass of :class:`Decision`.
"""


@dataclass
class Tagged(Generic[TDecision]):
    tags: list[str]
    decision: TDecision
    uuid: str = field(default_factory=lambda: str(uuid4()))


T = TypeVar("T")
P = ParamSpec("P")


class MetaPerspective(ABCMeta):
    pass


class Perspective(ABC, Generic[TDecision], metaclass=MetaPerspective):
    last_known_position: int | None
    new_decisions: list[Tagged[TDecision]]

    def __new__(cls, *_: Any, **__: Any) -> Self:
        self = super().__new__(cls)
        self.last_known_position = None
        self.new_decisions = []
        return self

    @abstractmethod
    def consistency_boundary(self) -> Selector | Sequence[Selector]:
        raise NotImplementedError  # pragma: no cover

    def trigger_event(
        self,
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """
        Constructs new tagged decision and appends to list of uncommitted events.
        """
        tagged = Tagged[TDecision](
            tags=list(tags),
            decision=decision_cls(*args, **kwargs),
        )
        tagged.decision.mutate(self)
        self.new_decisions.append(tagged)

    def collect_events(self) -> Sequence[Tagged[Any]]:
        """
        Drains list of triggered events.
        """
        collected, self.new_decisions = self.new_decisions, []
        return collected


TPerspective = TypeVar("TPerspective", bound=Perspective[Any])


decorated_funcs: dict[tuple[MetaPerspective, type[Decision]], CallableType] = {}


class MetaSupportsEventDecorator(MetaPerspective):
    def __init__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, namespace)

        topic_prefix = construct_topic(cls) + "."

        cls.projected_types: list[type[Decision]] = []

        # Find the event decorators on this class.
        func_decorators = [
            decorator
            for decorator in all_func_decorators
            if construct_topic(decorator.decorated_func).startswith(topic_prefix)
        ]

        for decorator in func_decorators:
            given = decorator.given_event_cls

            # Keep things simple by only supporting given classes (not names).
            assert given is not None, "Event class not given"
            # TODO: Maybe support event name strings, maybe not....

            # Make sure given event class is a Decision subclass.
            assert issubclass(given, Decision)

            decorated_func_callers[decorator] = given

            # Remember which decorated func to call.
            decorated_funcs[(cls, given)] = decorator.decorated_func

            cls.projected_types.append(given)


class MetaEnduringObject(MetaSupportsEventDecorator):
    def __init__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, namespace)
        # Check a subclasse of EnduringObject has an __init__ method.
        if Perspective not in bases:
            try:
                init_method = namespace["__init__"]
            except KeyError:
                msg = f"Enduring object class {cls} has no __init__ method"
                raise ProgrammingError(msg) from None
            if not isinstance(init_method, CommandMethodDecorator):
                msg = (
                    f"Enduring object class {cls} __init__ method "
                    f"is not decorated with @event decorator"
                )
                raise ProgrammingError(msg) from None
            init_method.avoid_delegating_to_init_method = True

    def __call__(cls: type[T], **kwargs: Any) -> T:
        # TODO: For convenience, make this error out in the same way
        #  as it would if the arguments didn't match the __init__
        #  method and __init__was called directly, and verify the
        #  event's __init__ is valid when initialising the class,
        #  just like we do for event-sourced aggregates.

        assert issubclass(cls, EnduringObject)

        return cls._create(**kwargs)


TID = TypeVar("TID", bound=str, default=str)


class EnduringObject(
    Perspective[TDecision], Generic[TDecision, TID], metaclass=MetaEnduringObject
):
    id: TID

    @classmethod
    def _create(cls: type[Self], **kwargs: Any) -> Self:
        obj = cls.__new__(cls, **kwargs)
        # TODO: Maybe find a better way to do this, but it seems we need
        #  to set the `id` attribute for the call the `trigger_event()`?
        obj.id = next(iter(kwargs.values()))  # assume ID is first arg
        # Calling __init__ should trigger an event that
        # calls the original decorated __init__ method.
        obj.__init__(**kwargs)  # type: ignore[misc]
        return obj

    def consistency_boundary(self) -> list[Selector]:
        return [Selector(tags=[self.id])]

    def trigger_event(
        self,
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        tags = [self.id, *tags]
        super().trigger_event(decision_cls, tags, *args, **kwargs)


class Group(Perspective[TDecision]):
    _enduring_objects: list[EnduringObject]
    classes: ClassVar[Sequence[type[EnduringObject[Any, Any]]]]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        # 1. Get all the type hints from the __init__ method
        hints = typing.get_type_hints(cls.__init__)

        extracted_classes: list[type[EnduringObject[Any]]] = []

        for param_name, hint in hints.items():
            # Ignore the return type and 'self' (if it happens to be annotated)
            if param_name in ("return", "self"):
                continue

            # 2. Extract arguments from the Union
            # (e.g., Student | None becomes (Student, NoneType))
            args = typing.get_args(hint)

            if args:
                # Filter out NoneType to just get the actual class
                extracted_classes.extend(
                    arg for arg in args if arg is not types.NoneType
                )
            else:
                # If it wasn't a Union/Optional, just append the hint directly
                extracted_classes.append(hint)
        assert all(issubclass(cls, EnduringObject) for cls in extracted_classes)
        cls.classes = extracted_classes

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        self = super().__new__(cls, *args, **kwargs)
        self._enduring_objects = [a for a in args if isinstance(a, EnduringObject)]
        return self

    def consistency_boundary(self) -> list[Selector]:
        return [
            Selector(tags=cb.tags)
            for cbs in [o.consistency_boundary() for o in self._enduring_objects]
            for cb in cbs
        ]

    def trigger_event(
        self,
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        objs = self._enduring_objects
        tags = [o.id for o in objs] + list(tags)
        tagged = Tagged[TDecision](
            tags=tags,
            decision=decision_cls(*args, **kwargs),
        )
        for o in objs:
            tagged.decision.mutate(o)
        self.new_decisions.append(tagged)


@dataclass
class Selector:
    types: Sequence[type[Decision]] = ()
    tags: Sequence[str] = ()


class MetaSlice(MetaSupportsEventDecorator):
    def __init__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, namespace)
        cls.do_projection = len(cls.projected_types) != 0


class Slice(Perspective[TDecision], metaclass=MetaSlice):
    def execute(self) -> None:
        pass


TSlice = TypeVar("TSlice", bound=Slice[Any])
TGroup = TypeVar("TGroup", bound=Group[Any])
