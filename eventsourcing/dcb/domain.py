from __future__ import annotations

import sys
from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, cast
from uuid import uuid4

from typing_extensions import Self, TypeVar

from eventsourcing.domain import (
    AbstractDecision,
    AbstractDecoratedFuncCaller,
    CallableType,
    ProgrammingError,
    all_func_decorators,
    decorated_func_callers,
    filter_kwargs_for_method_params,
)
from eventsourcing.utils import construct_topic, get_topic, resolve_topic

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

_enduring_object_init_classes: dict[type[Any], type[InitialDecision]] = {}


class Decision(AbstractDecision):
    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    def mutate(self, obj: TPerspective | None) -> TPerspective | None:
        assert obj is not None
        self.apply(obj)
        return obj

    def apply(self, obj: Any) -> None:
        pass


class InitialDecision(Decision):
    originator_topic: str

    def mutate(self, obj: TPerspective | None) -> TPerspective | None:
        kwargs = self.as_dict()
        originator_type = resolve_topic(kwargs.pop("originator_topic"))
        if issubclass(originator_type, EnduringObject):
            enduring_object_id = kwargs.pop(self.id_attr_name(originator_type))
            try:
                enduring_object = type.__call__(originator_type, **kwargs)
            except TypeError as e:  # pragma: no cover
                msg = (
                    f"{type(self).__qualname__} cannot __init__ "
                    f"{originator_type.__qualname__} "
                    f"with kwargs {kwargs}: {e}"
                )
                raise TypeError(msg) from e
            enduring_object.id = enduring_object_id
            enduring_object.__post_init__()
            return enduring_object
        msg = f"Originator type not subclass of EnduringObject: {originator_type}"
        raise TypeError(msg)

    @classmethod
    def id_attr_name(cls, enduring_object_class: type[EnduringObject[Any, TID]]) -> TID:
        return cast(TID, f"{enduring_object_class.__name__.lower()}_id")


TDecision = TypeVar("TDecision", bound=Decision)
"""
A type variable representing any subclass of :class:`Decision`.
"""


class Tagged(Generic[TDecision]):
    def __init__(self, tags: list[str], decision: TDecision) -> None:
        self.tags = tags
        self.decision = decision


class DecoratedFuncCaller(Decision, AbstractDecoratedFuncCaller):
    def apply(self, obj: Perspective[Decision]) -> None:
        """Applies event by calling method decorated by @event."""

        # Identify the function that was decorated.
        try:
            decorated_func = decorated_funcs[(type(obj), type(self))]
        except KeyError:
            return

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

        # Call super method, just in case.
        super().apply(obj)


T = TypeVar("T")


class MetaPerspective(ABCMeta):
    pass


class Perspective(ABC, Generic[TDecision], metaclass=MetaPerspective):
    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        perspective = super().__new__(cls)
        perspective.__base_init__(*args, **kwargs)
        return perspective

    def __base_init__(self, *_: Any, **__: Any) -> None:
        self.last_known_position: int | None = None
        self.new_decisions: list[Tagged[TDecision]] = []

    def append_new_decision(self, *new_decisions: Tagged[TDecision]) -> None:
        self.new_decisions.extend(new_decisions)

    def collect_new_decisions(self) -> Sequence[Tagged[TDecision]]:
        collected, self.new_decisions = self.new_decisions, []
        return collected

    @property
    @abstractmethod
    def cb(self) -> Selector | Sequence[Selector]:
        raise NotImplementedError  # pragma: no cover


TPerspective = TypeVar("TPerspective", bound=Perspective[Any])


given_event_class_mapping: dict[type[Decision], type[DecoratedFuncCaller]] = {}
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

            # Decorator should not have an original event class that has already
            # been subclassed, unless it's mentioned twice in the same projection,
            # which should be caught as an error. Because it will have either
            # already been subclassed and replaced, or never been seen before.
            assert given not in given_event_class_mapping

            # Maybe redefine given event class as subclass of 'DecoratedFuncCaller'.
            if not issubclass(given, DecoratedFuncCaller):
                # Define a subclass of the given event class.
                func_caller = cls._insert_decorator_func_caller(given, topic_prefix)

                # Remember which subclass for given event class.
                given_event_class_mapping[given] = func_caller

            else:
                # Check we subclassed this class.
                assert given in given_event_class_mapping.values()
                func_caller = given

            # If command method, remember which event class to trigger.
            if not construct_topic(decorator.decorated_func).endswith("._"):
                decorated_func_callers[decorator] = func_caller

            # Remember which decorated func to call.
            decorated_funcs[(cls, func_caller)] = decorator.decorated_func

            cls.projected_types.append(func_caller)

    def _insert_decorator_func_caller(
        cls, given_event_class: type[Decision], topic_prefix: str
    ) -> type[DecoratedFuncCaller]:
        # Identify the context in which the given class is defined.
        context: ModuleType | type
        if "." not in given_event_class.__qualname__:
            # Looks like a non-nested class.
            context = sys.modules[given_event_class.__module__]
        elif construct_topic(given_event_class).startswith(topic_prefix):
            # Nested in this class.
            context = cls
        else:  # pragma: no cover
            # Nested in another class...
            # TODO: Write a test that does this....
            msg = f"Decorating {cls} with {given_event_class} is not supported"
            raise ProgrammingError(msg)

        # Check the context actually has the given event class.
        assert getattr(context, given_event_class.__name__) is given_event_class

        # Define subclass.
        func_caller = cast(
            type[DecoratedFuncCaller],
            type(
                given_event_class.__name__,
                (DecoratedFuncCaller, given_event_class),
                {
                    "__module__": cls.__module__,
                    "__qualname__": given_event_class.__qualname__,
                },
            ),
        )

        # Replace the given event class in the context.
        setattr(context, given_event_class.__name__, func_caller)

        return func_caller


class MetaEnduringObject(MetaSupportsEventDecorator):
    def __init__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, namespace)
        # Find and remember the "InitialDecision" class.
        for item in cls.__dict__.values():
            if isinstance(item, type) and issubclass(item, InitialDecision):
                _enduring_object_init_classes[cls] = item
                break

    def __call__(cls: type[T], **kwargs: Any) -> T:
        # TODO: For convenience, make this error out in the same way
        #  as it would if the arguments didn't match the __init__
        #  method and __init__was called directly, and verify the
        #  event's __init__ is valid when initialising the class,
        #  just like we do for event-sourced aggregates.

        assert issubclass(cls, EnduringObject)
        try:
            init_enduring_object_class = _enduring_object_init_classes[cls]
        except KeyError:
            msg = (
                f"Enduring object class {cls.__name__} has no "
                f"InitialDecision class. Please define a subclass of "
                f"InitialDecision as a nested class on {cls.__name__}."
            )
            raise ProgrammingError(msg) from None

        return cls._create(
            decision_cls=init_enduring_object_class,
            **kwargs,
        )


TID = TypeVar("TID", bound=str, default=str)


class EnduringObject(
    Perspective[TDecision], Generic[TDecision, TID], metaclass=MetaEnduringObject
):
    id: TID

    @classmethod
    def _create(
        cls: type[Self], decision_cls: type[InitialDecision], **kwargs: Any
    ) -> Self:
        enduring_object_id = cls._create_id()
        id_attr_name = decision_cls.id_attr_name(cls)
        assert id_attr_name not in kwargs
        assert "originator_topic" not in kwargs
        assert "tags" not in kwargs
        initial_kwargs: dict[str, Any] = {
            id_attr_name: enduring_object_id,
            "originator_topic": get_topic(cls),
        }
        initial_kwargs.update(kwargs)
        try:

            initialised = Tagged[TDecision](
                tags=[enduring_object_id],
                decision=cast(type[TDecision], decision_cls)(**initial_kwargs),
            )
        except TypeError as e:
            msg = (
                f"Unable to construct {decision_cls.__qualname__} event "
                f"with kwargs {initial_kwargs}: {e}"
            )
            raise TypeError(msg) from e
        enduring_object = cast(Self, initialised.decision.mutate(None))
        assert enduring_object is not None
        enduring_object.new_decisions += (initialised,)
        return enduring_object

    @classmethod
    def _create_id(cls) -> TID:
        return cast(TID, f"{cls.__name__.lower()}-{uuid4()}")

    def __post_init__(self) -> None:
        pass

    @property
    def cb(self) -> list[Selector]:
        return [Selector(tags=[self.id])]

    def trigger_event(
        self,
        decision_cls: type[Decision],
        *,
        tags: Sequence[str] = (),
        **kwargs: Any,
    ) -> None:
        tags = [self.id, *tags]
        assert issubclass(decision_cls, DecoratedFuncCaller), decision_cls
        decision = Tagged[DecoratedFuncCaller](
            tags=tags,
            decision=decision_cls(**kwargs),
        )
        decision.decision.mutate(self)
        self.new_decisions += (cast(Tagged[TDecision], decision),)


class Group(Perspective[TDecision]):
    def __base_init__(self, *args: Any, **kwargs: Any) -> None:
        super().__base_init__(*args, **kwargs)
        self._enduring_objects = [a for a in args if isinstance(a, EnduringObject)]

    @property
    def cb(self) -> list[Selector]:
        return [
            Selector(tags=cb.tags)
            for cbs in [o.cb for o in self._enduring_objects]
            for cb in cbs
        ]

    def trigger_event(
        self,
        decision_cls: type[TDecision],
        *,
        tags: Sequence[str] = (),
        **kwargs: Any,
    ) -> None:
        objs = self.enduring_objects
        tags = [o.id for o in objs] + list(tags)
        decision = Tagged[TDecision](
            tags=tags,
            decision=decision_cls(**kwargs),
        )
        for o in objs:
            decision.decision.mutate(o)
        self.new_decisions += (decision,)

    @property
    def enduring_objects(self) -> Sequence[EnduringObject[TDecision]]:
        return [o for o in self.__dict__.values() if isinstance(o, EnduringObject)]

    def collect_new_decisions(self) -> Sequence[Tagged[TDecision]]:
        group_events = list(super().collect_new_decisions())
        for o in self.enduring_objects:
            group_events.extend(o.collect_new_decisions())
        return group_events


@dataclass
class Selector:
    types: Sequence[type[Decision]] = ()
    tags: Sequence[str] = ()


class MetaSlice(MetaSupportsEventDecorator):
    pass


class Slice(Perspective[TDecision], metaclass=MetaSlice):
    do_projection = True

    def execute(self) -> None:
        pass


TSlice = TypeVar("TSlice", bound=Slice[Any])
TGroup = TypeVar("TGroup", bound=Group[Any])
