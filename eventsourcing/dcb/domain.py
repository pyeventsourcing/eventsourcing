from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, ParamSpec, cast
from uuid import uuid4

from typing_extensions import Self, TypeVar

from eventsourcing.domain import (
    AbstractDecision,
    CallableType,
    ProgrammingError,
    all_func_decorators,
    decorated_func_callers,
    filter_kwargs_for_method_params,
)
from eventsourcing.utils import construct_topic, get_topic, resolve_topic

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_enduring_object_init_classes: dict[type[Any], type[InitialDecision]] = {}


class Decision(AbstractDecision):
    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

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


class InitialDecision(Decision):
    originator_topic: str

    def mutate(self, obj: TPerspective | None) -> TPerspective | None:
        # Identify the function that was decorated.
        if obj is not None:
            try:
                decorated_func = decorated_funcs[(type(obj), type(self))]
            except KeyError:  # pragma: no cover
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
                return obj

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


T = TypeVar("T")
P = ParamSpec("P")


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

    def trigger_event(
        self,
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        tagged = Tagged[TDecision](
            tags=list(tags),
            decision=decision_cls(*args, **kwargs),
        )
        tagged.decision.mutate(self)
        self.append_new_decision(tagged)


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

            # If command method, remember which event class to trigger.
            if not construct_topic(decorator.decorated_func).endswith("._"):
                decorated_func_callers[decorator] = given

            # Remember which decorated func to call.
            decorated_funcs[(cls, given)] = decorator.decorated_func

            cls.projected_types.append(given)


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

            initial_tagged_decision = Tagged[TDecision](
                tags=[enduring_object_id],
                decision=cast(type[TDecision], decision_cls)(**initial_kwargs),
            )
        except TypeError as e:
            msg = (
                f"Unable to construct {decision_cls.__qualname__} event "
                f"with kwargs {initial_kwargs}: {e}"
            )
            raise TypeError(msg) from e
        enduring_object = cast(Self, initial_tagged_decision.decision.mutate(None))
        assert enduring_object is not None
        enduring_object.new_decisions += (initial_tagged_decision,)
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
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        tags = [self.id, *tags]
        super().trigger_event(decision_cls, tags, *args, **kwargs)


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
        decision_cls: Callable[P, TDecision],
        tags: Sequence[str] = (),
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        objs = self.enduring_objects
        tags = [o.id for o in objs] + list(tags)
        decision = Tagged[TDecision](
            tags=tags,
            decision=decision_cls(*args, **kwargs),
        )
        for o in objs:
            decision.decision.mutate(o)
        self.append_new_decision(decision)

    @property
    def enduring_objects(self) -> Sequence[EnduringObject[TDecision]]:
        return [o for o in self.__dict__.values() if isinstance(o, EnduringObject)]


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
