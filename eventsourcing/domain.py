from __future__ import annotations

import contextvars
import inspect
import os
import typing
from abc import ABC, ABCMeta, abstractmethod
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, tzinfo
from functools import cache
from types import FunctionType, NoneType, WrapperDescriptorType, new_class
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    ParamSpec,
    Protocol,
    Self,
    TypeVar,
    cast,
    overload,
    runtime_checkable,
)
from uuid import UUID, uuid4

from eventsourcing.errors import ProgrammingError
from eventsourcing.utils import (
    construct_topic,
    get_method_name,
    resolve_multi_generic_target,
    resolve_topic,
    to_snake_case,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


TZINFO: tzinfo = resolve_topic(os.getenv("TZINFO_TOPIC", "datetime:timezone.utc"))
NIL_UUID = UUID("00000000-0000-0000-0000-000000000000")
NIL_UUID_STR = str(NIL_UUID)


def datetime_now_with_tzinfo() -> datetime:
    """
    Constructs a timezone-aware :class:`datetime`
    object for the current date and time.

    Uses :py:obj:`TZINFO` as the timezone.
    """
    return datetime.now(tz=TZINFO)


_ctx_event_metadata: contextvars.ContextVar[dict[str, str] | None] = (
    contextvars.ContextVar("ctx_event_metadata", default=None)
)


def get_metadata_from_context() -> dict[str, str]:
    """
    Copies metadata dict from context variable. Used to initialise event attribute.
    """
    current = _ctx_event_metadata.get()
    return current.copy() if current is not None else {}


@contextmanager
def put_metadata_in_context(metadata: dict[str, str]) -> Iterator[None]:
    """
    Updates metadata dict in context variable. Use this in your request handlers.
    """
    token: contextvars.Token[dict[str, str] | None] | None = None
    try:
        existing = _ctx_event_metadata.get() or {}
        merged_metadata = {**existing, **metadata}
        token = _ctx_event_metadata.set(merged_metadata)
        yield
    finally:
        if token is not None:
            _ctx_event_metadata.reset(token)
        else:
            pass  # pragma: no cover


@contextmanager
def set_metadata_in_context(metadata: dict[str, str]) -> Iterator[None]:
    """
    Overrides metadata dict in context variable. Used when mutating perspectives.
    """
    token: contextvars.Token[dict[str, str] | None] | None = None
    try:
        token = _ctx_event_metadata.set(metadata)
        yield
    finally:
        if token is not None:
            _ctx_event_metadata.reset(token)
        else:
            pass  # pragma: no cover


@contextmanager
def null_metadata_in_context() -> Iterator[None]:
    """
    Masks metadata with an empty dict. Used when reconstructing domain events.
    """
    token: contextvars.Token[dict[str, str] | None] | None = None
    try:
        token = _ctx_event_metadata.set({})
        yield
    finally:
        if token is not None:
            _ctx_event_metadata.reset(token)
        else:
            pass  # pragma: no cover


_T = TypeVar("_T")


class AbstractDecision(ABC):
    @abstractmethod
    def as_dict(self) -> dict[str, Any]:
        pass  # pragma: no cover

    def mutate(self, obj: _T | None) -> _T | None:
        assert obj is not None

        # Identify the function that was decorated.
        if decorated_func := decorated_funcs.get((type(obj), type(self))):
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

    def apply(self, obj: Any) -> None:  # noqa: B027
        pass


TDecision = TypeVar("TDecision", bound=AbstractDecision)
"""
A type variable representing any subclass of :class:`Decision`.
"""

TDecision_co = TypeVar("TDecision_co", bound=AbstractDecision, covariant=True)
"""
A covariant type variable representing any subclass of :class:`Decision`.
"""


@dataclass(kw_only=True)
class EventEnvelope(Generic[TDecision_co]):
    decision: TDecision_co
    uuid: UUID = field(default_factory=uuid4)
    metadata: dict[str, str] = field(default_factory=get_metadata_from_context)

    def mutate(self, obj: _T | None) -> _T | None:
        with set_metadata_in_context(self.metadata):
            return self.decision.mutate(obj)


TEnvelope = TypeVar("TEnvelope", bound=EventEnvelope[Any])

TPerspective = TypeVar("TPerspective", bound="Perspective[Any]")


@dataclass(kw_only=True)
class TaggedEvent(EventEnvelope[TDecision_co]):
    tags: list[str]


EventSpecType = str | type[AbstractDecision]
CallableType = Callable[..., None]
DecoratableType = CallableType | property
TDecoratableType = TypeVar("TDecoratableType", bound=DecoratableType)

decorated_funcs: dict[tuple[type[Any], type[AbstractDecision]], CallableType] = {}


class CommandMethodDecorator:
    def __init__(
        self,
        event_spec: EventSpecType | None,
        decorated_obj: DecoratableType,
        event_topic: str | None = None,
    ):

        self.is_name_inferred_from_method = False
        self.given_event_cls: type[AbstractDecision] | None = None
        self.given_event_name: str | None = None
        self.decorated_property: property | None = None
        self.is_property_setter = False
        self.property_setter_arg_name: str | None = None
        self.decorated_func: CallableType
        self.event_topic = event_topic
        self.avoid_delegating_to_init_method = False

        # Event name has been specified.
        if isinstance(event_spec, str):
            if event_spec == "":
                msg = "Can't use empty string as name of event class"
                raise ValueError(msg)
            self.given_event_name = event_spec

        # Event class has been specified.
        elif isinstance(event_spec, type) and issubclass(event_spec, AbstractDecision):
            # # Guard against associating more than
            # # one method body with any given class.
            # if (
            #     issubclass(event_spec, CanMutateAggregate)
            #     and event_spec in _given_event_classes
            # ):
            #     name = event_spec.__name__
            #     msg = f"{name} event class used in more than one decorator"
            #     raise TypeError(msg)
            self.given_event_cls = event_spec
            # _given_event_classes.add(event_spec)

        # Process a decorated property.
        if isinstance(decorated_obj, property):
            # Disallow putting event decorator on property getter.
            if decorated_obj.fset is None:
                assert decorated_obj.fget, "Property has no getter"
                method_name = decorated_obj.fget.__name__
                msg = f"@event can't decorate {method_name}() property getter"
                raise TypeError(msg)

            # Remember we are decorating a property.
            self.decorated_property = decorated_obj

            # TODO: Disallow unusual property setters in more detail.
            assert isinstance(decorated_obj.fset, FunctionType)

            # Disallow deriving event class names from property names.
            if not self.given_event_cls and not self.given_event_name:
                method_name = decorated_obj.fset.__name__
                msg = (
                    f"@event decorator on @{method_name}.setter "
                    f"requires event name or class"
                )
                raise TypeError(msg)

            # Remember property "setter" as the decorated function.
            self.decorated_func = decorated_obj.fset

            # Remember the name of the second setter arg.
            setter_arg_names = list(inspect.signature(self.decorated_func).parameters)
            assert len(setter_arg_names) == 2
            self.property_setter_arg_name = setter_arg_names[1]

        # Process a decorated function.
        elif isinstance(decorated_obj, FunctionType):
            # Remember the decorated obj as the decorated method.
            self.decorated_func = decorated_obj

            all_func_decorators.append(self)
            # If necessary, derive an event class name from the method.
            if not self.given_event_cls and not self.given_event_name:
                original_method_name = self.decorated_func.__name__
                if original_method_name != "__init__":
                    self.is_name_inferred_from_method = True
                    self.given_event_name = "".join(
                        [s.capitalize() for s in original_method_name.split("_")]
                    )

        # Disallow decorating other types of object.
        else:
            msg = f"{decorated_obj} is not a function or property"
            raise TypeError(msg)

        # Disallow using methods with variable params to define event class.
        if self.given_event_name:
            _raise_type_error_if_func_has_variable_params(self.decorated_func)

        # Disallow using methods with positional only params to define event class.
        if self.given_event_name:
            _raise_type_error_if_func_has_positional_only_params(self.decorated_func)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        # Initialised decorator was called directly, presumably by
        # a decorating property that has this decorator as its fset.
        # So trigger an event.
        assert self.is_property_setter
        assert self.property_setter_arg_name
        assert len(args) == 2
        assert len(kwargs) == 0
        assert isinstance(args[0], Aggregate)
        aggregate_instance = args[0]
        bound = BoundCommandMethodDecorator(self, aggregate_instance)
        # TODO: Possibly unnecessary to construct kwargs,
        #  maybe try passing value as positional arg.
        property_setter_arg_value = args[1]
        kwargs = {self.property_setter_arg_name: property_setter_arg_value}
        bound.trigger(**kwargs)

    @overload
    def __get__(
        self, instance: None, owner: type[SupportsEventDecorator[Any]]
    ) -> UnboundCommandMethodDecorator | property:
        """
        Descriptor protocol for getting decorated method or property on class object.
        """

    @overload
    def __get__(
        self,
        instance: SupportsEventDecorator[Any],
        owner: type[SupportsEventDecorator[Any]],
    ) -> BoundCommandMethodDecorator | Any:
        """
        Descriptor protocol for getting decorated method or property on instance object.
        """

    def __get__(
        self,
        instance: SupportsEventDecorator[Any] | None,
        owner: type[SupportsEventDecorator[Any]],
    ) -> BoundCommandMethodDecorator | UnboundCommandMethodDecorator | property | Any:
        """Descriptor protocol for getting decorated method or property."""
        if self.decorated_func.__name__ == "_":
            msg = "Underscore 'non-command' methods cannot be used to trigger events."
            raise ProgrammingError(msg)

        # If we are decorating a property, then delegate to the property's __get__.
        if self.decorated_property:
            return self.decorated_property.__get__(instance, owner)

        # If we are decorating an __init__ method, then delegate to the __init__ method.
        if (
            self.decorated_func.__name__ == "__init__"
            and not self.avoid_delegating_to_init_method
        ):
            return self.decorated_func.__get__(instance, owner)

        # Return a "bound" command method decorator if we have an instance.
        if instance:
            return BoundCommandMethodDecorator(self, instance)

        if "SPHINX_BUILD" in os.environ:  # pragma: no cover
            # Sphinx hack: use the original function when sphinx is running so that the
            # documentation ends up with the correct function signatures.
            # See 'SPHINX_BUILD' in conf.py.
            return self.decorated_func

        # Return an "unbound" command method decorator if we have no instance.
        return UnboundCommandMethodDecorator(self)

    def __set__(self, instance: SupportsEventDecorator[Any], value: Any) -> None:
        """Descriptor protocol for assigning to decorated property."""
        # Set decorated property indirectly by triggering an event.
        # TODO: Possibly unnecessary to construct kwargs,
        #  maybe try passing value as positional arg.
        assert self.property_setter_arg_name
        b = BoundCommandMethodDecorator(self, instance)
        kwargs = {self.property_setter_arg_name: value}
        b.trigger(**kwargs)


# 1. Overload for when you pass an event specification (e.g., @event(Created))
@overload
def event(
    arg: EventSpecType | None = None, /, *, topic: str | None = None
) -> Callable[[TDecoratableType], TDecoratableType]: ...


# 2. Overload for when you use it directly as a decorator (e.g., @event)
@overload
def event(
    arg: TDecoratableType, /, *, topic: str | None = None
) -> TDecoratableType: ...


def event(
    arg: EventSpecType | TDecoratableType | None = None, /, *, topic: str | None = None
) -> TDecoratableType | Callable[[TDecoratableType], TDecoratableType]:
    """Event-triggering decorator for aggregate command methods and property setters.

    Can be used to decorate an aggregate method or property setter so that an
    event will be triggered when the method is called or the property is set.
    The body of the method will be used to apply the event to the aggregate,
    both when the event is triggered and when the aggregate is reconstructed
    from stored events.

    .. code-block:: python

        class MyAggregate(Aggregate):
            @event("NameChanged")
            def set_name(self, name: str):
                self.name = name

    ...is equivalent to...

    .. code-block:: python

        class MyAggregate(Aggregate):
            def set_name(self, name: str):
                self.trigger_event(self.NameChanged, name=name)

            class NameChanged(Aggregate.Event):
                name: str

                def apply(self, aggregate):
                    aggregate.name = self.name

    In the example above, the event "NameChanged" is defined automatically
    by inspecting the signature of the ``set_name()`` method. If it is
    preferred to declare the event class explicitly, for example to define
    upcasting of old events, the event class itself can be mentioned in the
    event decorator rather than just providing the name of the event as a
    string.

    .. code-block:: python

        class MyAggregate(Aggregate):

            class NameChanged(Aggregate.Event):
                name: str

            @event(NameChanged)
            def set_name(self, name: str):
                aggregate.name = self.name


    """
    if isinstance(arg, (FunctionType, property)):
        command_method_decorator = CommandMethodDecorator(
            event_spec=None,
            decorated_obj=arg,
        )
        return cast(
            "Callable[[TDecoratableType], TDecoratableType]", command_method_decorator
        )

    if (
        arg is None
        or isinstance(arg, str)
        or (isinstance(arg, type) and issubclass(arg, AbstractDecision))
    ):
        event_spec = arg

        def create_command_method_decorator(
            decorated_obj: TDecoratableType,
        ) -> TDecoratableType:
            command_method_decorator = CommandMethodDecorator(
                event_spec=event_spec,
                decorated_obj=decorated_obj,
                event_topic=topic,
            )
            return cast("TDecoratableType", command_method_decorator)

        return create_command_method_decorator

    msg = (
        f"{arg} is not a str, function, property, or subclass of "
        f"{AbstractDecision.__name__}"
    )
    raise TypeError(msg)


triggers = event


class UnboundCommandMethodDecorator:
    """Wraps a CommandMethodDecorator instance when accessed on an aggregate class."""

    def __init__(self, event_decorator: CommandMethodDecorator):
        """:param CommandMethodDecorator event_decorator:"""
        self.event_decorator = event_decorator
        self.__module__ = event_decorator.decorated_func.__module__
        self.__name__ = event_decorator.decorated_func.__name__
        self.__qualname__ = event_decorator.decorated_func.__qualname__
        self.__annotations__ = event_decorator.decorated_func.__annotations__
        self.__doc__ = event_decorator.decorated_func.__doc__
        # self.__wrapped__ = event_decorator.decorated_method
        # functools.update_wrapper(self, event_decorator.decorated_method)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        # TODO: Review this, because other subclasses of BaseAggregate might too....
        # Expect first argument is an aggregate instance.
        if len(args) < 1 or not isinstance(args[0], Aggregate):
            msg = "Expected aggregate as first argument"
            raise TypeError(msg)
        aggregate: SupportsEventDecorator[Any] = args[0]
        assert isinstance(aggregate, SupportsEventDecorator)
        BoundCommandMethodDecorator(self.event_decorator, aggregate)(
            *args[1:], **kwargs
        )


class BoundCommandMethodDecorator:
    """Binds a CommandMethodDecorator with an object instance that can trigger
    events, so that calls to decorated command methods can be intercepted and
    will trigger a "decorated func caller" event.
    """

    def __init__(
        self, event_decorator: CommandMethodDecorator, obj: SupportsEventDecorator[Any]
    ):
        """:param CommandMethodDecorator event_decorator:
        :param Aggregate aggregate:
        """
        self.event_decorator = event_decorator
        self.__module__ = event_decorator.decorated_func.__module__
        self.__name__ = event_decorator.decorated_func.__name__
        self.__qualname__ = event_decorator.decorated_func.__qualname__
        self.__annotations__ = event_decorator.decorated_func.__annotations__
        self.__doc__ = event_decorator.decorated_func.__doc__
        self.obj = obj

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.trigger(*args, **kwargs)

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        coerced_kwargs = _coerce_args_to_kwargs(
            self.event_decorator.decorated_func, args, kwargs
        )
        try:
            event_cls = decorated_func_callers[self.event_decorator]
        except KeyError as e:  # pragma: no cover
            msg = (
                f"Event class not registered for event decorator on "
                f"{self.event_decorator.decorated_func.__qualname__}"
            )
            raise KeyError(msg) from e
        filtered_kwargs = filter_kwargs_for_method_params(coerced_kwargs, event_cls)
        self.obj.trigger_event(event_cls, **filtered_kwargs)


# _given_event_classes = set[type]()
decorated_func_callers: dict[CommandMethodDecorator, type[AbstractDecision]] = {}
all_func_decorators: list[CommandMethodDecorator] = []


def _raise_type_error_if_func_has_variable_params(method: CallableType) -> None:
    for param in inspect.signature(method).parameters.values():
        if param.kind is param.VAR_POSITIONAL:
            msg = f"*{param.name} not supported by decorator on {method.__name__}()"
            raise TypeError(msg)
            # TODO: Support VAR_POSITIONAL?
            # annotations["__star_args__"] = "typing.Any"

        if param.kind is param.VAR_KEYWORD:
            # TODO: Support VAR_KEYWORD?
            # annotations["__star_kwargs__"] = "typing.Any"
            msg = f"**{param.name} not supported by decorator on {method.__name__}()"
            raise TypeError(msg)


def _raise_type_error_if_func_has_positional_only_params(method: CallableType) -> None:
    # TODO: Support POSITIONAL_ONLY?
    positional_only_params = []
    for param in inspect.signature(method).parameters.values():
        if param.name == "self":
            continue
        if param.kind is param.POSITIONAL_ONLY:
            positional_only_params.append(param.name)

    if positional_only_params:
        msg = (
            f"positional only args arg not supported by @event decorator on "
            f"{method.__name__}(): {', '.join(positional_only_params)}"
        )
        raise TypeError(msg)


def _coerce_args_to_kwargs(
    target_method: CallableType,
    args: Iterable[Any],
    kwargs: dict[str, Any],
    *,
    expects_id: bool = False,
) -> dict[str, Any]:
    # __init__ methods are WrapperDescriptorType, other method are FunctionType.
    if isinstance(target_method, BoundCommandMethodDecorator):
        target_method = target_method.event_decorator.decorated_func
    assert isinstance(
        target_method,
        (FunctionType, WrapperDescriptorType, BoundCommandMethodDecorator),
    ), target_method

    args = tuple(args)
    enumerated_args_names, keyword_defaults_items = _spec_coerce_args_to_kwargs(
        method=target_method,
        len_args=len(args),
        kwargs_keys=tuple(kwargs.keys()),
        expects_id=expects_id,
    )

    copy_kwargs = dict(kwargs)
    copy_kwargs.update({name: args[i] for i, name in enumerated_args_names})
    copy_kwargs.update(keyword_defaults_items)
    return copy_kwargs


@cache
def _spec_coerce_args_to_kwargs(
    method: CallableType,
    len_args: int,
    kwargs_keys: tuple[str],
    *,
    expects_id: bool,
) -> tuple[tuple[tuple[int, str], ...], tuple[tuple[str, Any], ...]]:
    method_signature = inspect.signature(method)
    positional_names = []
    keyword_defaults = {}
    required_positional = []
    required_keyword_only = []
    if expects_id:
        positional_names.append("id")
        required_positional.append("id")
    for name, param in method_signature.parameters.items():
        if name == "self":
            continue
        # elif param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
        if param.kind is param.KEYWORD_ONLY:
            required_keyword_only.append(name)
        if param.kind is param.POSITIONAL_OR_KEYWORD:
            positional_names.append(name)
            if param.default == param.empty:
                required_positional.append(name)
        if param.default != param.empty:
            keyword_defaults[name] = param.default
    # if not required_keyword_only and not positional_names:
    #     if args or kwargs:
    #         raise TypeError(f"{method.__name__}() takes no args")
    method_name = get_method_name(method)
    for name in kwargs_keys:
        if name not in required_keyword_only and name not in positional_names:
            msg = f"{method_name}() got an unexpected keyword argument '{name}'"
            raise TypeError(msg)
    if len_args > len(positional_names):
        msg = (
            f"{method_name}() takes {len(positional_names) + 1} "
            f"positional argument{'' if len(positional_names) + 1 == 1 else 's'} "
            f"but {len_args + 1} were given"
        )
        raise TypeError(msg)
    required_positional_not_in_kwargs = [
        n for n in required_positional if n not in kwargs_keys
    ]
    num_missing = len(required_positional_not_in_kwargs) - len_args
    if num_missing > 0:
        missing_names = [
            f"'{name}'" for name in required_positional_not_in_kwargs[len_args:]
        ]
        msg = (
            f"{method_name}() missing {num_missing} required positional "
            f"argument{'' if num_missing == 1 else 's'}: "
        )
        _raise_missing_names_type_error(missing_names, msg)
    args_names = []
    for counter, name in enumerate(positional_names):
        if counter + 1 > len_args:
            break
        if name in kwargs_keys:
            msg = f"{method_name}() got multiple values for argument '{name}'"
            raise TypeError(msg)
        args_names.append(name)
    missing_keyword_only_arguments = [
        name for name in required_keyword_only if name not in kwargs_keys
    ]
    if missing_keyword_only_arguments:
        missing_names = [f"'{name}'" for name in missing_keyword_only_arguments]
        msg = (
            f"{method_name}() missing {len(missing_names)} "
            "required keyword-only argument"
            f"{'' if len(missing_names) == 1 else 's'}: "
        )
        _raise_missing_names_type_error(missing_names, msg)
    for key in tuple(keyword_defaults.keys()):
        if key in args_names or key in kwargs_keys:
            keyword_defaults.pop(key)
    enumerated_args_names = tuple(enumerate(args_names))
    keyword_defaults_items = tuple(keyword_defaults.items())
    return enumerated_args_names, keyword_defaults_items


def _raise_missing_names_type_error(missing_names: list[str], msg: str) -> None:
    msg += missing_names[0]
    if len(missing_names) == 2:
        msg += f" and {missing_names[1]}"
    elif len(missing_names) > 2:
        msg += ", " + ", ".join(missing_names[1:-1])
        msg += f", and {missing_names[-1]}"
    raise TypeError(msg)


class WorksWithDecisions(Generic[TDecision]):
    works_with_decision_type: type[Any] | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Initialises subclass by identifying which decision class it works with.
        """
        super().__init_subclass__(**kwargs)

        # Find the type arg for TDecision.
        if "works_with_decision_type" not in cls.__dict__:
            type_args = resolve_multi_generic_target(cls, WorksWithDecisions)
            assert len(type_args) == 1, type_args
            resolved_decision_type = type_args[0]

            # if not _is_valid_id_type(resolved_originator_id_type):
            #     msg = f"Aggregate ID type arg cannot be {resolved_originator_id_type}"
            #     raise TypeError(msg)

            cls.works_with_decision_type = resolved_decision_type

    @classmethod
    def check_decision_type(cls, decision_cls: Any) -> None:
        if cls.works_with_decision_type is None:
            msg = f"{cls} has no decision type argument"
            raise TypeError(msg)
        requirement = getattr(decision_cls, "works_with_decision_type", decision_cls)
        if requirement is None:
            msg = f"{decision_cls} has no decision type argument"
            raise TypeError(msg)

        if not issubclass(requirement, cls.works_with_decision_type):
            msg = f"{requirement} mismatches {cls.works_with_decision_type}"
            raise TypeError(msg)


_P = ParamSpec("_P")


class Perspective(WorksWithDecisions[TDecision], ABC):
    last_known_position: int | None
    new_decisions: list[TaggedEvent[TDecision]]

    def __new__(cls, *_: Any, **__: Any) -> Self:
        self = super().__new__(cls)
        self.last_known_position = None
        self.new_decisions = []
        return self

    @abstractmethod
    def consistency_boundary(
        self,
    ) -> Selector[TDecision] | Sequence[Selector[TDecision]]:
        raise NotImplementedError  # pragma: no cover

    def trigger_event(
        self,
        decision_cls: Callable[_P, TDecision],
        tags: Sequence[str] = (),
        /,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """
        Constructs new event and appends to list of uncommitted events.
        """
        self.check_decision_type(decision_cls)
        envelope = TaggedEvent[TDecision](
            tags=list(tags),
            decision=decision_cls(*args, **kwargs),
        )
        envelope.mutate(self)
        self.new_decisions.append(envelope)

    def collect_events(self) -> Sequence[TaggedEvent[Any]]:
        """
        Drains list of triggered events.
        """
        collected, self.new_decisions = self.new_decisions, []
        return collected


class SupportsEventDecorator(WorksWithDecisions[TDecision]):
    projected_types: ClassVar[list[type[TDecision]]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        topic_prefix = construct_topic(cls) + "."

        cls.projected_types = []

        # Find the event decorators on this class.
        func_decorators = [
            decorator
            for decorator in all_func_decorators
            if construct_topic(decorator.decorated_func).startswith(topic_prefix)
        ]

        for decorator in func_decorators:
            if decorator.given_event_cls:
                decision_cls = cast(type[TDecision], decorator.given_event_cls)
                cls.check_decision_type(decision_cls)

            else:
                assert decorator.given_event_name
                if decorator.given_event_name not in cls.__dict__:
                    assert cls.works_with_decision_type
                    decision_cls = cls._define_event_class(
                        name=decorator.given_event_name,
                        bases=(cls.works_with_decision_type,),
                        apply_method=decorator.decorated_func,
                    )
                    setattr(cls, decorator.given_event_name, decision_cls)
                else:
                    decision_cls = cls.__dict__[decorator.given_event_name]

            decorated_func_callers[decorator] = decision_cls

            # Remember which decorated func to call.
            decorated_funcs[(cls, decision_cls)] = decorator.decorated_func

            cls.projected_types.append(decision_cls)

        # Support @property on @event.
        for attr_name, attr_value in tuple(cls.__dict__.items()):

            # Handle @property.setter decorator on top of @event decorator.
            if isinstance(attr_value, property) and isinstance(
                attr_value.fset, CommandMethodDecorator
            ):
                event_decorator = attr_value.fset
                # Inspect the setter method.
                method_signature = inspect.signature(event_decorator.decorated_func)
                assert len(method_signature.parameters) == 2
                event_decorator.is_property_setter = True
                event_decorator.property_setter_arg_name = list(
                    method_signature.parameters
                )[1]
                if event_decorator.decorated_func.__name__ != attr_name:
                    attr = cls.__dict__[event_decorator.decorated_func.__name__]
                    if isinstance(attr, CommandMethodDecorator):
                        # This is the "x = property(getx, setx) form" where setx
                        # is a decorated method.
                        continue
                        # Otherwise, it's "x = property(getx, event(setx))".
                elif event_decorator.is_name_inferred_from_method:
                    # This is the "@property.setter \ @event" form. We don't want
                    # event class name inferred from property (not past participle).
                    method_name = event_decorator.decorated_func.__name__
                    msg = (
                        f"@event decorator under @{method_name}.setter "
                        "requires event name or class"
                    )
                    raise TypeError(msg)

    @classmethod
    def _define_event_class(
        cls,
        name: str,
        bases: tuple[Any, ...],
        apply_method: CallableType | None,
        event_topic: str | None = None,
    ) -> type[TDecision]:
        # Define annotations for the event class (specs the init method).
        cls_annotations = {}
        if apply_method is not None:
            method_signature = inspect.signature(apply_method)
            super_annotations = {}

            for b in reversed(bases):
                actual_base = typing.get_origin(b) or b
                # Fallback to a tuple of just the base if __mro__ is somehow missing
                mro = getattr(actual_base, "__mro__", (actual_base,))

                for mro_cls in reversed(mro):
                    # Safely get the annotations dict for this specific class in the
                    # chain and update our running dictionary.
                    super_annotations.update(inspect.get_annotations(mro_cls))

            for param_name, param in list(method_signature.parameters.items())[1:]:
                # Don't define 'id' on a "created" class.
                if param_name == "id" and apply_method.__name__ == "__init__":
                    continue
                # Don't override super class annotations, unless no default on param.
                if param_name not in super_annotations or param.default == param.empty:
                    cls_annotations[param_name] = param.annotation or "typing.Any"
        event_cls_qualname = f"{cls.__qualname__}.{name}"
        event_cls_dict = {
            "__annotations__": cls_annotations,
            "__module__": cls.__module__,
            "__qualname__": event_cls_qualname,
            # FIX: Explicitly inject __orig_bases__ to prevent MRO attribute leakage
            # from base classes that were previously parameterized.
            "__orig_bases__": bases,
        }
        if event_topic:
            event_cls_dict["TOPIC"] = event_topic

        def populate_namespace(ns: dict[str, Any]) -> None:
            ns.update(event_cls_dict)

        # Create the event class object.
        _new_class = new_class(name, bases, exec_body=populate_namespace)
        return cast(type[TDecision], _new_class)

    def trigger_event(
        self,
        decision_cls: Any,
        tags: Sequence[str] = (),
        /,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError


class MetaCallTriggersEvent(ABCMeta):
    def __call__(cls: type[_T], *args: Any, **kwargs: Any) -> _T:
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


class CallTriggersEvent(
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


class EnduringObject(Perspective[TDecision], CallTriggersEvent[TDecision]):
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
    def _create(cls: type[Self], *args: Any, **kwargs: Any) -> Self:
        obj = cls.__new__(cls)
        init_kwargs = _coerce_args_to_kwargs(obj.__init__, args, kwargs)  # type: ignore[misc]
        id_kwargs = filter_kwargs_for_method_params(init_kwargs, cls.create_id)
        obj.id = init_kwargs.get(cls.continuity_id_name) or cls.create_id(**id_kwargs)
        # Calling __init__ should trigger an event that
        # calls the original decorated __init__ method.
        obj.__init__(*args, **kwargs)  # type: ignore[misc]
        return obj

    def consistency_boundary(self) -> list[Selector[TDecision]]:
        return [Selector(tags=[self.id])]

    def trigger_event(
        self,
        decision_cls: Callable[_P, TDecision],
        tags: Sequence[str] = (),
        /,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        if self.continuity_id_name not in kwargs:
            kwargs[self.continuity_id_name] = self.id
        super().trigger_event(decision_cls, [self.id, *tags], *args, **kwargs)


class Group(Perspective[TDecision]):
    _enduring_objects: list[EnduringObject[TDecision]]
    classes: ClassVar[Sequence[type[EnduringObject[TDecision]]]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
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

    def consistency_boundary(self) -> list[Selector[TDecision]]:
        return [
            Selector[TDecision](tags=cb.tags)
            for cbs in [o.consistency_boundary() for o in self._enduring_objects]
            for cb in cbs
        ]

    def trigger_event(
        self,
        decision_cls: Callable[_P, TDecision],
        tags: Sequence[str] = (),
        /,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        objs = self._enduring_objects
        tags = [o.id for o in objs] + list(tags)
        event = TaggedEvent[TDecision](
            tags=tags,
            decision=decision_cls(*args, **kwargs),
        )
        for o in objs:
            event.mutate(o)
        self.new_decisions.append(event)


@dataclass
class Selector(Generic[TDecision_co]):
    types: Sequence[type[TDecision_co]] = ()
    tags: Sequence[str] = ()


class Slice(Perspective[TDecision], SupportsEventDecorator[TDecision], ABC):
    do_projection: ClassVar[bool]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.do_projection = len(cls.projected_types) != 0

    def execute(self) -> None:
        pass


TSlice = TypeVar("TSlice", bound=Slice[Any])
TGroup = TypeVar("TGroup", bound=Group[Any])


def filter_kwargs_for_method_params(
    kwargs: dict[str, Any], method: Callable[..., Any]
) -> dict[str, Any]:
    names = _spec_filter_kwargs_for_method_params(method)
    return {k: v for k, v in kwargs.items() if k in names}


@cache
def _spec_filter_kwargs_for_method_params(method: Callable[..., Any]) -> set[str]:
    method_signature = inspect.signature(method)
    return set(method_signature.parameters)


TAggregate = TypeVar("TAggregate", bound="Aggregate[Any]")


@dataclass(kw_only=True)
class AggregateEvent(EventEnvelope[TDecision_co]):
    originator_id: str
    originator_version: int

    def mutate(self, obj: _T | None) -> _T | None:
        assert isinstance(obj, Aggregate)
        if obj.id == NIL_UUID_STR:
            # We received a shell, so initialise the `id` and `version`.
            obj.id = self.originator_id
            obj.version = self.originator_version

            # Apply the event to the aggregate.
            super().mutate(obj)

        else:
            # Check this event belongs to this aggregate.
            assert self.originator_id == obj.id, (self.originator_id, obj.id)
            # Check this event is the next one for this aggregate.
            assert self.originator_version == obj.version + 1, (
                self.originator_version,
                obj.version,
            )
            # Apply the event to the aggregate (allow for exceptions to be raised
            # before mutating any values).
            super().mutate(obj)

            # Increment the version number.
            obj.version = self.originator_version

        return obj


class Aggregate(CallTriggersEvent[TDecision]):
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

    def collect_events(self) -> Sequence[AggregateEvent[TDecision]]:
        """
        Drains list of triggered events.
        """
        collected, self.new_decisions = self.new_decisions, []
        return collected

    @classmethod
    def _create(cls: type[Self], *args: Any, **kwargs: Any) -> Self:
        obj = cls.__new__(cls, *args, **kwargs)
        # create_id_kwargs = filter_kwargs_for_method_params(
        #     _coerce_args_to_kwargs(cls.create_id, args, kwargs),
        #     cls.create_id,
        # )
        create_id_kwargs = filter_kwargs_for_method_params(kwargs, cls.create_id)
        obj.id = cls.create_id(**create_id_kwargs)
        # Calling __init__ should trigger an event that
        # calls the original decorated __init__ method.
        obj.__init__(*args, **kwargs)  # type: ignore[misc]
        return obj

    @classmethod
    def create_id(cls, *_: Any, **__: Any) -> str:
        return str(uuid4())

    def trigger_event(
        self,
        decision_cls: Callable[_P, TDecision],
        *args: _P.args,
        **kwargs: _P.kwargs,
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


ProjectorFunction = Callable[
    [_T | None, Iterable[TEnvelope]],
    _T | None,
]

MutatorFunction = Callable[
    [TEnvelope, _T | None],
    _T | None,
]


def projector(
    mutator: MutatorFunction[TEnvelope, _T],
) -> ProjectorFunction[_T, TEnvelope]:
    def projector_function(obj: _T | None, events: Iterable[TEnvelope]) -> _T | None:
        for e in events:
            obj = mutator(e, obj)
        return obj

    return projector_function


@projector
def evolve_aggregate(
    envelope: TEnvelope,
    obj: _T | None,
) -> _T | None:
    return envelope.mutate(obj)


@runtime_checkable
class CollectEventsProtocol(Protocol[TDecision_co]):
    """Protocol for aggregates that support collecting pending events."""

    def collect_events(self) -> Sequence[AggregateEvent[TDecision_co]]:
        """Returns a sequence of events."""
        raise NotImplementedError  # pragma: no cover


@runtime_checkable
class CanMutateProtocol(Protocol):
    """Protocol for events that have a mutate method."""

    def mutate(self, _: TAggregate | None) -> TAggregate | None:
        """
        Evolves the state of the given aggregate, either by
        returning the given aggregate instance with modified attributes
        or by constructing and returning a new aggregate instance.
        """
