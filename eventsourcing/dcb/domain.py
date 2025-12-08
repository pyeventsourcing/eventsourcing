from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, cast
from uuid import uuid4

from typing_extensions import Self, TypeVar

from eventsourcing.domain import (
    AbstractDCBEvent,
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

_enduring_object_init_classes: dict[type[Any], type[Initialises]] = {}


class Mutates(AbstractDCBEvent):
    def _as_dict(self) -> dict[str, Any]:
        raise NotImplementedError  # pragma: no cover

    def mutate(self, obj: TPerspective | None) -> TPerspective | None:
        assert obj is not None
        self.apply(obj)
        return obj

    def apply(self, obj: Any) -> None:
        pass


class Initialises(Mutates):
    originator_topic: str

    def mutate(self, obj: TPerspective | None) -> TPerspective | None:
        kwargs = self._as_dict()
        originator_topic = resolve_topic(kwargs.pop("originator_topic"))
        enduring_object_cls = cast(type[EnduringObject[Any]], originator_topic)
        enduring_object_id = kwargs.pop(self.id_attr_name(enduring_object_cls))
        try:
            enduring_object = type.__call__(enduring_object_cls, **kwargs)
        except TypeError as e:  # pragma: no cover
            msg = (
                f"{type(self).__qualname__} cannot __init__ "
                f"{enduring_object_cls.__qualname__} "
                f"with kwargs {kwargs}: {e}"
            )
            raise TypeError(msg) from e
        enduring_object.id = enduring_object_id
        enduring_object.__post_init__()
        return enduring_object

    @classmethod
    def id_attr_name(cls, enduring_object_class: type[EnduringObject[Any, TID]]) -> TID:
        return cast(TID, f"{enduring_object_class.__name__.lower()}_id")


TMutates = TypeVar("TMutates", bound=Mutates)


class Tagged(Generic[TMutates]):
    def __init__(self, tags: list[str], mutates: TMutates) -> None:
        self.tags = tags
        self.mutates = mutates


class DecoratedFuncCaller(Mutates, AbstractDecoratedFuncCaller):
    def apply(self, obj: Perspective[Mutates]) -> None:
        """Applies event by calling method decorated by @event."""

        # Identify the function that was decorated.
        try:
            decorated_func = decorated_funcs[(type(obj), type(self))]
        except KeyError:
            return

        # Select event attributes mentioned in function signature.
        self_dict = self._as_dict()
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


class MetaPerspective(type):
    pass


class Perspective(Generic[TMutates], metaclass=MetaPerspective):
    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        perspective = super().__new__(cls)
        perspective.__base_init__(*args, **kwargs)
        return perspective

    def __base_init__(self, *_: Any, **__: Any) -> None:
        self.last_known_position: int | None = None
        self.new_decisions: list[Tagged[TMutates]] = []

    def append(self, *new_decisions: Tagged[TMutates]) -> None:
        self.new_decisions.extend(new_decisions)

    def collect_events(self) -> Sequence[Tagged[TMutates]]:
        collected, self.new_decisions = self.new_decisions, []
        return collected

    @property
    def cb(self) -> Selector | Sequence[Selector]:
        raise NotImplementedError  # pragma: no cover


TPerspective = TypeVar("TPerspective", bound=Perspective[Any])


given_event_class_mapping: dict[type[Mutates], type[DecoratedFuncCaller]] = {}
decorated_funcs: dict[tuple[MetaPerspective, type[Mutates]], CallableType] = {}


class MetaSupportsEventDecorator(MetaPerspective):
    def __init__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, namespace)

        topic_prefix = construct_topic(cls) + "."

        cls.projected_types: list[type[Mutates]] = []

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

            # Make sure given event class is a Mutates subclass.
            assert issubclass(given, Mutates)

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
        cls, given_event_class: type[Mutates], topic_prefix: str
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
        # Find and remember the "initialises" class.
        for item in cls.__dict__.values():
            if isinstance(item, type) and issubclass(item, Initialises):
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
                f"Initialises class. Please define a subclass of "
                f"Initialises as a nested class on {cls.__name__}."
            )
            raise ProgrammingError(msg) from None

        return cls._create(
            decision_cls=init_enduring_object_class,
            **kwargs,
        )


TID = TypeVar("TID", bound=str, default=str)


class EnduringObject(
    Perspective[TMutates], Generic[TMutates, TID], metaclass=MetaEnduringObject
):
    id: TID

    @classmethod
    def _create(
        cls: type[Self], decision_cls: type[Initialises], **kwargs: Any
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

            initialised = Tagged[TMutates](
                tags=[enduring_object_id],
                mutates=cast(type[TMutates], decision_cls)(**initial_kwargs),
            )
        except TypeError as e:
            msg = (
                f"Unable to construct {decision_cls.__qualname__} event "
                f"with kwargs {initial_kwargs}: {e}"
            )
            raise TypeError(msg) from e
        enduring_object = cast(Self, initialised.mutates.mutate(None))
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
        decision_cls: type[Mutates],
        *,
        tags: Sequence[str] = (),
        **kwargs: Any,
    ) -> None:
        tags = [self.id, *tags]
        assert issubclass(decision_cls, DecoratedFuncCaller), decision_cls
        decision = Tagged[DecoratedFuncCaller](
            tags=tags,
            mutates=decision_cls(**kwargs),
        )
        decision.mutates.mutate(self)
        self.new_decisions += (cast(Tagged[TMutates], decision),)


class Group(Perspective[TMutates]):
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
        decision_cls: type[TMutates],
        *,
        tags: Sequence[str] = (),
        **kwargs: Any,
    ) -> None:
        objs = self.enduring_objects
        tags = [o.id for o in objs] + list(tags)
        decision = Tagged[TMutates](
            tags=tags,
            mutates=decision_cls(**kwargs),
        )
        for o in objs:
            decision.mutates.mutate(o)
        self.new_decisions += (decision,)

    @property
    def enduring_objects(self) -> Sequence[EnduringObject[TMutates]]:
        return [o for o in self.__dict__.values() if isinstance(o, EnduringObject)]

    def collect_events(self) -> Sequence[Tagged[TMutates]]:
        group_events = list(super().collect_events())
        for o in self.enduring_objects:
            group_events.extend(o.collect_events())
        return group_events


@dataclass
class Selector:
    types: Sequence[type[Mutates]] = ()
    tags: Sequence[str] = ()


class MetaSlice(MetaSupportsEventDecorator):
    pass


class Slice(Perspective[TMutates], metaclass=MetaSlice):
    do_projection = True

    def execute(self) -> None:
        pass


TSlice = TypeVar("TSlice", bound=Slice[Any])
TGroup = TypeVar("TGroup", bound=Group[Any])
