import inspect
import os
from abc import ABC, ABCMeta
from dataclasses import dataclass
from datetime import datetime, tzinfo
from functools import lru_cache
from types import FunctionType, WrapperDescriptorType
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID, uuid4

from eventsourcing.utils import get_method_name, get_topic, resolve_topic

# noinspection SpellCheckingInspection
TZINFO: tzinfo = resolve_topic(os.getenv("TZINFO_TOPIC", "datetime:timezone.utc"))


class MetaDomainEvent(ABCMeta):
    def __new__(
        mcs, name: str, bases: Tuple[type, ...], cls_dict: Dict[str, Any]
    ) -> "MetaDomainEvent":
        event_cls = super().__new__(mcs, name, bases, cls_dict)
        event_cls = dataclass(frozen=True)(event_cls)  # type: ignore
        return event_cls


T = TypeVar("T")


class DomainEvent(ABC, Generic[T], metaclass=MetaDomainEvent):
    """
    Base class for domain events, such as aggregate :class:`AggregateEvent`
    and aggregate :class:`Snapshot`.
    """

    originator_id: UUID
    originator_version: int
    timestamp: datetime

    def mutate(self, aggregate: Optional[T]) -> Optional[T]:
        """Abstract mutator method."""

    @staticmethod
    def create_timestamp() -> datetime:
        """
        Returns a timezone aware :class:`~datetime.datetime` object
        that is created by calling :class:`~datetime.datetime.now()`.
        """
        return datetime.now(tz=TZINFO)


TDomainEvent = TypeVar("TDomainEvent", bound=DomainEvent[Any])
TAggregate = TypeVar("TAggregate", bound="Aggregate")


class AggregateEvent(DomainEvent[TAggregate]):
    """
    Base class for aggregate events. Subclasses will model
    decisions made by the domain model aggregates.
    """

    def mutate(self, aggregate: Optional[TAggregate]) -> Optional[TAggregate]:
        """
        Changes the state of the aggregate
        according to domain event attributes.
        """
        assert aggregate is not None

        # Check this event belongs to this aggregate.
        if self.originator_id != aggregate.id:
            raise OriginatorIDError(self.originator_id, aggregate.id)

        # Check this event is the next in its sequence.
        next_version = aggregate.version + 1
        if self.originator_version != next_version:
            raise OriginatorVersionError(self.originator_version, next_version)

        # Call apply() before mutating values, in case exception is raised.
        self.apply(aggregate)

        # Update the aggregate version.
        aggregate.version = self.originator_version

        # Update the modified time.
        aggregate.modified_on = self.timestamp

        # Return the mutated aggregate.
        return aggregate

    def apply(self, aggregate: TAggregate) -> None:
        """
        Applies the domain event to the aggregate.
        """


class AggregateCreated(AggregateEvent[TAggregate]):
    # noinspection PyUnresolvedReferences
    """
    Domain event for when aggregate is created.

    Constructor arguments:

    :param UUID originator_id: ID of originating aggregate.
    :param int originator_version: version of originating aggregate.
    :param datetime timestamp: date-time of the event
    :param str originator_topic: topic for the aggregate class
    """

    originator_topic: str

    def mutate(self, aggregate: Optional[TAggregate]) -> Optional[TAggregate]:
        """
        Constructs aggregate instance defined
        by domain event object attributes.
        """
        assert aggregate is None

        # Resolve originator topic.
        aggregate_class: Type[TAggregate] = resolve_topic(
            self.__dict__["originator_topic"]
        )

        # Construct and return aggregate object.
        agg = aggregate_class.__new__(aggregate_class)

        # Separate the base class keywords arguments.
        base_kwargs = _filter_kwargs_for_method_params(
            self.__dict__, type(agg).__base_init__
        )

        # Call the base class init method.
        agg.__base_init__(**base_kwargs)

        # Select values that aren't mentioned in the method signature.
        init_kwargs = _filter_kwargs_for_method_params(
            self.__dict__, type(agg).__init__
        )

        # Provide the id, if the init method expects it.
        if aggregate_class in _init_mentions_id:
            init_kwargs["id"] = self.__dict__["originator_id"]

        # Call the aggregate class init method.
        agg.__init__(**init_kwargs)  # type: ignore

        self.apply(agg)

        return agg


class EventSourcingError(Exception):
    """
    Base exception class.
    """


class ProgrammingError(EventSourcingError):
    """
    Exception class for domain model programming errors.
    """


class LogEvent(DomainEvent[None]):
    """
    Base class for the events of event-sourced logs.
    """

    def mutate(self, aggregate: None) -> None:
        """Raises a ProgrammingError exception if called."""
        raise ProgrammingError("Log events cannot be projected into aggregates")


TLogEvent = TypeVar("TLogEvent", bound=LogEvent)


def _filter_kwargs_for_method_params(
    kwargs: Dict[str, Any], method: Callable[..., Any]
) -> Dict[str, Any]:
    names = _spec_filter_kwargs_for_method_params(method)
    return {k: v for k, v in kwargs.items() if k in names}


@lru_cache(maxsize=None)
def _spec_filter_kwargs_for_method_params(method: Callable[..., Any]) -> Set[str]:
    method_signature = inspect.signature(method)
    return set(method_signature.parameters)


EventSpecType = Optional[Union[str, Type[AggregateEvent[Any]]]]
AnyCallable = Callable[..., None]
DecoratedObjType = TypeVar("DecoratedObjType", bound=Union[AnyCallable, property])
InjectEventType = bool


class CommandMethodDecorator:
    def __init__(
        self,
        event_spec: EventSpecType,
        decorated_obj: DecoratedObjType,
    ):
        self.is_name_inferred_from_method = False
        self.given_event_cls: Optional[Type[AggregateEvent[Any]]] = None
        self.event_cls_name: Optional[str] = None
        self.decorated_property: Optional[property] = None
        self.is_property_setter = False
        self.property_setter_arg_name: Optional[str] = None
        self.decorated_method: Union[FunctionType, WrapperDescriptorType]

        # Event name has been specified.
        if isinstance(event_spec, str):
            if event_spec == "":
                raise ValueError("Can't use empty string as name of event class")
            self.event_cls_name = event_spec

        # Event class has been specified.
        elif isinstance(event_spec, type) and issubclass(event_spec, AggregateEvent):
            if event_spec in given_event_classes:
                name = event_spec.__name__
                raise TypeError(f"{name} event class used in more than one decorator")
            self.given_event_cls = event_spec
            given_event_classes.add(event_spec)

        # Process a decorated property.
        if isinstance(decorated_obj, property):

            # Disallow putting event decorator on property getter.
            if decorated_obj.fset is None:
                assert decorated_obj.fget, "Property has no getter"
                method_name = decorated_obj.fget.__name__
                raise TypeError(
                    f"@event can't decorate {method_name}() property getter"
                )

            # Remember we are decorating a property.
            self.decorated_property = decorated_obj

            # Remember the decorated method as the "setter" of the property.
            self.decorated_method = cast(FunctionType, decorated_obj.fset)

            assert isinstance(self.decorated_method, FunctionType)

            # Disallow deriving event class names from property names.
            if not self.given_event_cls and not self.event_cls_name:
                method_name = self.decorated_method.__name__
                raise TypeError(
                    f"@event on {method_name}() setter requires event name or class"
                )

            # Remember the name of the second setter arg.
            setter_arg_names = list(inspect.signature(self.decorated_method).parameters)
            assert len(setter_arg_names) == 2
            self.property_setter_arg_name = setter_arg_names[1]

        # Process a decorated method.
        elif isinstance(decorated_obj, FunctionType):

            # Remember the decorated method as the decorated object.
            self.decorated_method = decorated_obj

            # If necessary, derive an event class name from the method.
            if not self.given_event_cls and not self.event_cls_name:
                original_method_name = self.decorated_method.__name__
                if original_method_name != "__init__":
                    self.is_name_inferred_from_method = True
                    self.event_cls_name = "".join(
                        [s.capitalize() for s in original_method_name.split("_")]
                    )

        # Disallow decorating other types of object.
        else:
            raise TypeError(f"{decorated_obj} is not a function or property")

        # Disallow using methods with variable params to define event class.
        if self.event_cls_name:
            _check_no_variable_params(self.decorated_method)

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
        property_setter_arg_value = args[1]
        kwargs = {self.property_setter_arg_name: property_setter_arg_value}
        bound.trigger(**kwargs)

    @overload
    def __get__(
        self, instance: None, owner: "MetaAggregate"
    ) -> Union["UnboundCommandMethodDecorator", property]:
        ...  # pragma: no cover

    @overload
    def __get__(
        self, instance: "Aggregate", owner: "MetaAggregate"
    ) -> Union["BoundCommandMethodDecorator", Any]:
        ...  # pragma: no cover

    def __get__(
        self, instance: Optional["Aggregate"], owner: "MetaAggregate"
    ) -> Union[
        "BoundCommandMethodDecorator", "UnboundCommandMethodDecorator", property, Any
    ]:
        # If we are decorating a property, then delegate to the property's __get__.
        if self.decorated_property:
            return self.decorated_property.__get__(instance, owner)

        # Return a "bound" command method decorator if we have an instance.
        elif instance:
            return BoundCommandMethodDecorator(self, instance)

        # Return an "unbound" command method decorator if we have no instance.
        else:
            return UnboundCommandMethodDecorator(self)

    def __set__(self, instance: "Aggregate", value: Any) -> None:
        # Set decorated property indirectly by triggering an event.
        assert self.property_setter_arg_name
        b = BoundCommandMethodDecorator(self, instance)
        kwargs = {self.property_setter_arg_name: value}
        b.trigger(**kwargs)


# Called because specifying decorator params.
@overload
def event(arg: EventSpecType = None) -> Callable[[DecoratedObjType], DecoratedObjType]:
    ...  # pragma: no cover


# Called because Python is actually decorating something.
@overload
def event(arg: DecoratedObjType) -> DecoratedObjType:
    ...  # pragma: no cover


def event(
    arg: Union[EventSpecType, DecoratedObjType] = None,
) -> Union[Callable[[DecoratedObjType], DecoratedObjType], DecoratedObjType]:
    """
    Can be used to decorate an aggregate method so that when the
    method is called an event is triggered. The body of the method
    will be used to apply the event to the aggregate, both when the
    event is triggered and when the aggregate is reconstructed from
    stored events.

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
    by inspecting the signature of the `set_name()` method. If it is
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
            Callable[[DecoratedObjType], DecoratedObjType], command_method_decorator
        )

    elif (
        arg is None
        or isinstance(arg, str)
        or isinstance(arg, type)
        and issubclass(arg, AggregateEvent)
    ):
        event_spec = arg

        def create_command_method_decorator(
            decorated_obj: DecoratedObjType,
        ) -> DecoratedObjType:
            command_method_decorator = CommandMethodDecorator(
                event_spec=event_spec,
                decorated_obj=decorated_obj,
            )
            return cast(DecoratedObjType, command_method_decorator)

        return create_command_method_decorator

    else:
        raise TypeError(
            f"{arg} is not a str, aggregate event class, function, or property"
        )


triggers = event


class UnboundCommandMethodDecorator:
    """
    Wraps an EventDecorator instance when attribute is accessed
    on an aggregate class.
    """

    def __init__(self, event_decorator: CommandMethodDecorator):
        """

        :param CommandMethodDecorator event_decorator:
        """
        self.event_decorator = event_decorator
        assert event_decorator.decorated_method
        self.__qualname__ = event_decorator.decorated_method.__qualname__
        self.__name__ = event_decorator.decorated_method.__name__


class BoundCommandMethodDecorator:
    """
    Wraps an EventDecorator instance when attribute is accessed
    on an aggregate so that the aggregate methods can be accessed.
    """

    def __init__(
        self, event_decorator: CommandMethodDecorator, aggregate: "TAggregate"
    ):
        """

        :param CommandMethodDecorator event_decorator:
        :param Aggregate aggregate:
        """
        assert event_decorator.decorated_method
        self.event_decorator = event_decorator
        self.__qualname__ = event_decorator.decorated_method.__qualname__
        self.__name__ = event_decorator.decorated_method.__name__
        self.aggregate = aggregate

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        assert isinstance(self.event_decorator, CommandMethodDecorator)  # for PyCharm
        assert self.event_decorator.decorated_method
        kwargs = _coerce_args_to_kwargs(
            self.event_decorator.decorated_method, args, kwargs
        )
        event_cls = decorated_event_classes[self.event_decorator]
        kwargs = _filter_kwargs_for_method_params(
            kwargs, event_cls.__dict__["__init__"]
        )
        self.aggregate.trigger_event(event_cls, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.trigger(*args, **kwargs)


given_event_classes: Set[type] = set()
decorated_methods: Dict[type, AnyCallable] = {}
aggregate_has_many_created_event_classes: Dict[type, List[str]] = {}


class DecoratedEvent(AggregateEvent[Any]):
    def apply(self, aggregate: "TAggregate") -> None:
        """
        Applies event to aggregate by calling method decorated by @event.
        """
        # Call super method, just in case any base classes need it.
        super().apply(aggregate)

        # Identify the method that was decorated.
        decorated_method = decorated_methods[type(self)]

        # Select event attributes mentioned in method signature.
        kwargs = _filter_kwargs_for_method_params(self.__dict__, decorated_method)

        # Call the original method with event attribute values.
        decorated_method(aggregate, **kwargs)


decorated_event_classes: Dict[CommandMethodDecorator, Type[DecoratedEvent]] = {}


def _check_no_variable_params(method: FunctionType) -> None:
    for param in inspect.signature(method).parameters.values():
        if param.kind is param.VAR_POSITIONAL:
            raise TypeError(
                f"*{param.name} not supported by decorator on {method.__name__}()"
            )
            # Todo: Support VAR_POSITIONAL?
            # annotations["__star_args__"] = "typing.Any"

        if param.kind is param.VAR_KEYWORD:
            # Todo: Support VAR_KEYWORD?
            # annotations["__star_kwargs__"] = "typing.Any"
            raise TypeError(
                f"**{param.name} not supported by decorator on {method.__name__}()"
            )


def _coerce_args_to_kwargs(
    method: Union[FunctionType, WrapperDescriptorType],
    args: Iterable[Any],
    kwargs: Dict[str, Any],
    expects_id: bool = False,
) -> Dict[str, Any]:
    assert isinstance(method, (FunctionType, WrapperDescriptorType))

    args = tuple(args)
    enumerated_args_names, keyword_defaults_items = _spec_coerce_args_to_kwargs(
        method=method,
        len_args=len(args),
        kwargs_keys=tuple(kwargs.keys()),
        expects_id=expects_id,
    )

    copy_kwargs = dict(kwargs)
    for i, name in enumerated_args_names:
        copy_kwargs[name] = args[i]
    for name, value in keyword_defaults_items:
        copy_kwargs[name] = value
    return copy_kwargs


@lru_cache(maxsize=None)
def _spec_coerce_args_to_kwargs(
    method: Union[FunctionType, WrapperDescriptorType],
    len_args: int,
    kwargs_keys: Tuple[str],
    expects_id: bool,
) -> Tuple[Tuple[Tuple[int, str], ...], Tuple[Tuple[str, Any], ...]]:
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
            raise TypeError(
                f"{method_name}() got an unexpected " f"keyword argument '{name}'"
            )
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
        raise_missing_names_type_error(missing_names, msg)
    counter = 0
    args_names = []
    for name in positional_names:
        if counter + 1 > len_args:
            break
        if name in kwargs_keys:
            raise TypeError(
                f"{method_name}() got multiple values for argument '{name}'"
            )
        else:
            args_names.append(name)
            counter += 1
    missing_keyword_only_arguments = []
    for name in required_keyword_only:
        if name not in kwargs_keys:
            missing_keyword_only_arguments.append(name)
    if missing_keyword_only_arguments:
        missing_names = [f"'{name}'" for name in missing_keyword_only_arguments]
        msg = (
            f"{method_name}() missing {len(missing_names)} "
            f"required keyword-only argument"
            f"{'' if len(missing_names) == 1 else 's'}: "
        )
        raise_missing_names_type_error(missing_names, msg)
    for key in tuple(keyword_defaults.keys()):
        if key in args_names or key in kwargs_keys:
            keyword_defaults.pop(key)
    enumerated_args_names = tuple(enumerate(args_names))
    keyword_defaults_items = tuple(keyword_defaults.items())
    return enumerated_args_names, keyword_defaults_items


def raise_missing_names_type_error(missing_names: List[str], msg: str) -> None:
    msg += missing_names[0]
    if len(missing_names) == 2:
        msg += f" and {missing_names[1]}"
    elif len(missing_names) > 2:
        msg += ", " + ", ".join(missing_names[1:-1])
        msg += f", and {missing_names[-1]}"
    raise TypeError(msg)


TT = TypeVar("TT", bound="type")

_annotations_mention_id: Set["MetaAggregate"] = set()
_init_mentions_id: Set["MetaAggregate"] = set()


class MetaAggregate(ABCMeta):
    INITIAL_VERSION = 1

    class Event(AggregateEvent[TAggregate]):
        pass

    class Created(Event[TAggregate], AggregateCreated[TAggregate]):
        pass

    _created_event_class: Type[AggregateCreated[Any]]

    def __new__(mcs: Type[TT], *args: Any, **kwargs: Any) -> TT:
        try:
            class_annotations = args[2]["__annotations__"]
        except KeyError:
            class_annotations = None
            annotations_mention_id = False
        else:
            try:
                class_annotations.pop("id")
            except KeyError:
                annotations_mention_id = False
            else:
                annotations_mention_id = True
        cls = ABCMeta.__new__(mcs, *args)
        if class_annotations:
            cls = dataclass(eq=False, repr=False)(cls)
        if annotations_mention_id:
            _annotations_mention_id.add(cls)
        return cls

    def __init__(
        cls,
        *args: Any,
        created_event_name: Optional[str] = None,
    ) -> None:
        super().__init__(*args)

        # Identify or define a base event class for this aggregate.
        base_event_name = "Event"
        try:
            base_event_cls = cls.__dict__[base_event_name]
        except KeyError:
            base_event_cls = cls._define_event_class(
                base_event_name, (cls.Event,), None
            )
            setattr(cls, base_event_name, base_event_cls)

        # Make sure all events defined on aggregate subclass the base event class.
        for name, value in tuple(cls.__dict__.items()):
            if name == base_event_name:
                # Don't subclass the base event class again.
                continue
            if name.lower() == name:
                # Don't subclass lowercase named attributes that have classes.
                continue
            if isinstance(value, type) and issubclass(value, AggregateEvent):
                if not issubclass(value, base_event_cls):
                    sub_class = cls._define_event_class(
                        name, (value, base_event_cls), None
                    )
                    setattr(cls, name, sub_class)

        # Identify or define the aggregate's "created" event class.
        created_event_class: Optional[Type[AggregateCreated[Any]]] = None

        # Has the "created" event class been indicated with '_created_event_class'.
        if "_created_event_class" in cls.__dict__:
            created_event_class = cls.__dict__["_created_event_class"]
            if isinstance(created_event_class, type) and issubclass(
                created_event_class, AggregateCreated
            ):
                # We just subclassed the event classes, so reassign this.
                created_event_class = getattr(cls, created_event_class.__name__)
                assert created_event_class
                cls._created_event_class = created_event_class
            else:
                raise TypeError(
                    f"{created_event_class} not subclass of {AggregateCreated.__name__}"
                )

        # Disallow using both '_created_event_class' and 'created_event_name'.
        if created_event_class and created_event_name:
            raise TypeError(
                "Can't use both '_created_event_class' and 'created_event_name'"
            )

        # Is the init method method decorated with a CommandMethodDecorator?
        if isinstance(cls.__dict__.get("__init__"), CommandMethodDecorator):
            init_decorator: CommandMethodDecorator = cls.__dict__["__init__"]

            # Set the original method on the class (un-decorate __init__).
            cls.__init__ = init_decorator.decorated_method  # type: ignore

            # Disallow using both 'created_event_name' and '_created_event_class'.
            if created_event_name:
                raise TypeError(
                    "Can't use both 'created_event_name' and decorator on __init__"
                )
            elif created_event_class:
                raise TypeError(
                    "Can't use both '_created_event_class' and decorator on __init__"
                )

            # Does the decorator specify a "create" event class?
            if init_decorator.given_event_cls:
                created_event_class = getattr(
                    cls, init_decorator.given_event_cls.__name__
                )
                if isinstance(created_event_class, type) and issubclass(
                    created_event_class, AggregateCreated
                ):
                    assert created_event_class
                    cls._created_event_class = created_event_class
                else:
                    raise TypeError(
                        f"{created_event_class} not subclass of "
                        f"{AggregateCreated.__name__}"
                    )

            # Does the decorator specify a "create" event name?
            elif init_decorator.event_cls_name:
                created_event_name = init_decorator.event_cls_name

            # Disallow using decorator on __init__ without event spec.
            else:
                raise TypeError(
                    "Decorator on __init__ has neither event name nor class"
                )

        # Todo: Write a test to cover this when "Created" class is explicitly defined.
        # Check if init mentions ID.
        for param_name in inspect.signature(cls.__init__).parameters:  # type: ignore
            if param_name == "id":
                _init_mentions_id.add(cls)
                break

        # If no "created" event class has been specified, find or create one.
        if created_event_class is None:

            # Discover all the "created" event classes already defined.
            created_event_classes: Dict[str, Type[AggregateCreated[Any]]] = {}
            for name, value in tuple(cls.__dict__.items()):
                if isinstance(value, type) and issubclass(value, AggregateCreated):
                    created_event_classes[name] = value

            # Is a "created" event class already defined that matches the name?
            if created_event_name in created_event_classes:
                cls._created_event_class = created_event_classes[created_event_name]

            # If there is only one class defined, and we have no name, use it.
            elif len(created_event_classes) == 1 and not created_event_name:
                cls._created_event_class = next(iter(created_event_classes.values()))

            # If there are no "created" event classes already defined, or a name is
            # specified that hasn't matched, then define a "created" event class.
            elif len(created_event_classes) == 0 or created_event_name:

                # If no "created" event name has been specified, use default name.
                if not created_event_name:
                    # This is safe because len(created_event_classes) == 0.
                    created_event_name = "Created"

                # Disallow init method from having variable params if
                # we are using it to define a "created" event class.
                try:
                    init_method = cls.__dict__["__init__"]
                except KeyError:
                    init_method = None
                else:
                    try:
                        _check_no_variable_params(init_method)
                    except TypeError:
                        raise

                # Define a "created" event class for this aggregate.
                if issubclass(cls.Created, base_event_cls):
                    # Don't subclass from base event class twice.
                    bases: Tuple[type, ...] = (cls.Created,)
                else:
                    bases = (cls.Created, base_event_cls)
                event_cls = cls._define_event_class(
                    created_event_name,
                    bases,
                    init_method,
                )

                # Set the event class as an attribute of the aggregate class.
                setattr(cls, created_event_name, event_cls)

                # Remember which is the "created" event class.
                cls._created_event_class = cast(Type[AggregateCreated[Any]], event_cls)

            # Prepare to disallow ambiguity of choice between created event classes.
            else:
                aggregate_has_many_created_event_classes[cls] = list(
                    created_event_classes
                )

        # Prepare the subsequent event classes.
        for attribute in tuple(cls.__dict__.values()):

            # Watch out for @property that sits over an @event.
            if isinstance(attribute, property) and isinstance(
                attribute.fset, CommandMethodDecorator
            ):
                attribute = attribute.fset
                if attribute.is_name_inferred_from_method:
                    # We don't want name inferred from property (not past participle).
                    method_name = attribute.decorated_method.__name__
                    raise TypeError(
                        f"@event under {method_name}() property setter requires event "
                        f"class name"
                    )
                # Attribute is a property decorating an event decorator.
                attribute.is_property_setter = True
                method_signature = inspect.signature(attribute.decorated_method)
                assert len(method_signature.parameters) == 2
                attribute.property_setter_arg_name = list(method_signature.parameters)[
                    1
                ]

            # Attribute is an event decorator, so define a "decorated" event.
            if isinstance(attribute, CommandMethodDecorator):

                if attribute.given_event_cls:
                    # Check this is not a "created" event class.
                    if issubclass(attribute.given_event_cls, AggregateCreated):
                        raise TypeError(
                            f"{attribute.given_event_cls} "
                            f"is subclass of AggregateCreated"
                        )

                    # Define event class as subclass of given class.
                    given_subclass = getattr(cls, attribute.given_event_cls.__name__)
                    event_cls = cls._define_event_class(
                        attribute.given_event_cls.__name__,
                        (DecoratedEvent, given_subclass),
                        None,
                    )

                else:
                    assert attribute.event_cls_name

                    # Check event class isn't already defined.
                    if attribute.event_cls_name in cls.__dict__:
                        raise TypeError(
                            f"{attribute.event_cls_name} "
                            f"event already defined on {cls.__name__}"
                        )

                    # Define event class from signature of original method.
                    event_cls = cls._define_event_class(
                        attribute.event_cls_name,
                        (DecoratedEvent, base_event_cls),
                        attribute.decorated_method,
                    )

                # Cache the decorated method for the event class to use.
                decorated_methods[event_cls] = attribute.decorated_method

                # Set the event class as an attribute of the aggregate class.
                setattr(cls, event_cls.__name__, event_cls)

                # Remember which event class to trigger.
                decorated_event_classes[attribute] = cast(
                    Type[DecoratedEvent], event_cls
                )

        # Check any create_id method defined on this class is static or class method.
        if "create_id" in cls.__dict__:
            if not isinstance(cls.__dict__["create_id"], (staticmethod, classmethod)):
                raise TypeError(
                    f"{cls.create_id} is not a static or class method: "
                    f"{type(cls.create_id)}"
                )

        # Get the parameters of the create_id method that will be used by this class.
        cls._create_id_param_names: List[str] = []
        for name, param in inspect.signature(cls.create_id).parameters.items():
            if param.kind in [param.KEYWORD_ONLY, param.POSITIONAL_OR_KEYWORD]:
                cls._create_id_param_names.append(name)

        # Define event classes for all events on bases.
        for aggregate_base_class in args[1]:
            for name, value in aggregate_base_class.__dict__.items():
                if (
                    isinstance(value, type)
                    and issubclass(value, AggregateEvent)
                    and name not in cls.__dict__
                    and name.lower() != name
                ):
                    sub_class = cls._define_event_class(
                        name, (base_event_cls, value), None
                    )
                    setattr(cls, name, sub_class)

    def _define_event_class(
        cls,
        name: str,
        bases: Tuple[type, ...],
        apply_method: Optional[AnyCallable],
    ) -> type:
        # Define annotations for the event class (specs the init method).
        annotations = {}
        if apply_method is not None:
            method_signature = inspect.signature(apply_method)
            supers = {
                s for b in bases for s in b.__mro__ if hasattr(s, "__annotations__")
            }
            super_annotations = {a for s in supers for a in s.__annotations__}
            for param_name, param in list(method_signature.parameters.items())[1:]:
                # Don't define 'id' on a "created" class.
                if param_name == "id" and apply_method.__name__ == "__init__":
                    continue
                # Don't override super class annotations, unless no default on param.
                if param_name not in super_annotations or param.default == param.empty:
                    annotations[param_name] = "typing.Any"  # Todo: Improve this?
        event_cls_qualname = ".".join([cls.__qualname__, name])
        event_cls_dict = {
            "__annotations__": annotations,
            "__module__": cls.__module__,
            "__qualname__": event_cls_qualname,
        }

        # Create the event class object.
        return type(name, bases, event_cls_dict)

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        try:
            created_event_classes = aggregate_has_many_created_event_classes[cls]
            raise TypeError(
                """Can't decide which of many "created" event classes to use: """
                f"""'{"', '".join(created_event_classes)}'. Please use class """
                "arg 'created_event_name' or @event decorator on __init__ method."
            )
        except KeyError:
            pass

        self_init: WrapperDescriptorType = cls.__init__  # type: ignore
        kwargs = _coerce_args_to_kwargs(
            self_init,
            args,
            kwargs,
            expects_id=cls in _annotations_mention_id,
        )
        return cls._create(
            event_class=cls._created_event_class,
            **kwargs,
        )

    def _create(
        cls,
        event_class: Type[AggregateCreated[TAggregate]],
        *,
        id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> TAggregate:
        """
        Factory method to construct a new
        aggregate object instance.
        """
        # Construct the domain event class,
        # with an ID and version, and the
        # a topic for the aggregate class.
        create_id_kwargs = {
            k: v for k, v in kwargs.items() if k in cls._create_id_param_names
        }
        originator_id = id or cls.create_id(**create_id_kwargs)

        # Impose the required common "created" event attribute values.
        kwargs = kwargs.copy()
        kwargs.update(
            originator_topic=get_topic(cls),
            originator_id=originator_id,
            originator_version=cls.INITIAL_VERSION,
            timestamp=event_class.create_timestamp(),
        )

        try:
            # noinspection PyArgumentList
            created_event = event_class(
                **kwargs,
            )
        except TypeError as e:
            msg = f"Unable to construct '{event_class.__name__}' event: {e}"
            raise TypeError(msg)
        # Construct the aggregate object.
        agg = created_event.mutate(None)

        assert agg is not None
        # Append the domain event to pending list.
        agg.pending_events.append(created_event)
        # Return the aggregate.
        return agg

    # noinspection PyUnusedLocal
    @staticmethod
    def create_id(**kwargs: Any) -> UUID:
        """
        Returns a new aggregate ID.
        """
        return uuid4()


class Aggregate(ABC, metaclass=MetaAggregate):
    """
    Base class for aggregate roots.
    """

    def __base_init__(
        self, originator_id: UUID, originator_version: int, timestamp: datetime
    ) -> None:
        """
        Initialises an aggregate object with an :data:`id`, a :data:`version`
        number, and a :data:`timestamp`.
        """
        self._id = originator_id
        self._version = originator_version
        self._created_on = timestamp
        self._modified_on = timestamp
        self._pending_events: List[AggregateEvent[Any]] = []

    @property
    def id(self) -> UUID:
        """
        The ID of the aggregate.
        """
        return self._id

    @property
    def version(self) -> int:
        """
        The version number of the aggregate.
        """
        return self._version

    @version.setter
    def version(self, version: int) -> None:
        # noinspection PyAttributeOutsideInit
        self._version = version

    @property
    def created_on(self) -> datetime:
        """
        The date and time when the aggregate was created.
        """
        return self._created_on

    @property
    def modified_on(self) -> datetime:
        """
        The date and time when the aggregate was last modified.
        """
        return self._modified_on

    @modified_on.setter
    def modified_on(self, modified_on: datetime) -> None:
        # noinspection PyAttributeOutsideInit
        self._modified_on = modified_on

    @property
    def pending_events(self) -> List[AggregateEvent[Any]]:
        """
        A list of pending events.
        """
        return self._pending_events

    class Event(AggregateEvent[TAggregate]):
        pass

    class Created(Event[TAggregate], AggregateCreated[TAggregate]):
        pass

    def __eq__(self, other: Any) -> bool:
        return type(self) == type(other) and self.__dict__ == other.__dict__

    def __repr__(self) -> str:
        attrs = [
            f"{k.lstrip('_')}={v!r}"
            for k, v in self.__dict__.items()
            if k != "_pending_events"
        ]
        return f"{type(self).__name__}({', '.join(attrs)})"

    def trigger_event(
        self,
        event_class: Type[AggregateEvent[Any]],
        **kwargs: Any,
    ) -> None:
        """
        Triggers domain event of given type, by creating
        an event object and using it to mutate the aggregate.
        """
        # Construct the domain event as the
        # next in the aggregate's sequence.
        # Use counting to generate the sequence.
        next_version = self.version + 1

        # Impose the required common domain event attribute values.
        kwargs = kwargs.copy()
        kwargs.update(
            originator_id=self.id,
            originator_version=next_version,
            timestamp=event_class.create_timestamp(),
        )
        try:
            new_event = event_class(**kwargs)
        except TypeError as e:
            raise TypeError(f"Can't construct event {event_class}: {e}")

        # Mutate aggregate with domain event.
        new_event.mutate(self)
        # Append the domain event to pending list.
        self.pending_events.append(new_event)

    def collect_events(self) -> List[AggregateEvent[Any]]:
        """
        Collects and returns a list of pending aggregate
        :class:`AggregateEvent` objects.
        """
        collected = []
        while self.pending_events:
            collected.append(self.pending_events.pop(0))
        return collected


# @overload
# def aggregate(*, created_event_name: str) -> Callable[[Any], Type[Aggregate]]:
#     ...
#
#
# @overload
# def aggregate(cls: Any) -> Type[Aggregate]:
#     ...


def aggregate(
    cls: Optional[Any] = None,
    *,
    created_event_name: Optional[str] = None,
) -> Union[Type[Aggregate], Callable[[Any], Type[Aggregate]]]:
    """
    Converts the class that was passed in to inherit from Aggregate.

    .. code-block:: python

        @aggregate
        class MyAggregate:
            pass

    ...is equivalent to...

    .. code-block:: python

        class MyAggregate(Aggregate):
            pass
    """

    def decorator(cls_: Any) -> Type[Aggregate]:
        if issubclass(cls_, Aggregate):
            raise TypeError(f"{cls_.__qualname__} is already an Aggregate")
        bases = cls_.__bases__
        if bases == (object,):
            bases = (Aggregate,)
        else:
            bases += (Aggregate,)
        cls_dict = dict()
        cls_dict.update(cls_.__dict__)
        cls_ = MetaAggregate(
            cls_.__qualname__,
            bases,
            cls_dict,
            created_event_name=created_event_name,
        )
        assert issubclass(cls_, Aggregate)
        return cls_

    if cls:
        return decorator(cls)
    else:
        return decorator


class OriginatorIDError(EventSourcingError):
    """
    Raised when a domain event can't be applied to
    an aggregate due to an ID mismatch indicating
    the domain event is not in the aggregate's
    sequence of events.
    """


class OriginatorVersionError(EventSourcingError):
    """
    Raised when a domain event can't be applied to
    an aggregate due to version mismatch indicating
    the domain event is not the next in the aggregate's
    sequence of events.
    """


class VersionError(OriginatorVersionError):
    """
    Old name for 'OriginatorVersionError'.

    This class exists to maintain backwards-compatibility
    but will be removed in a future version Please use
    'OriginatorVersionError' instead.
    """


class Snapshot(DomainEvent[TAggregate]):
    # noinspection PyUnresolvedReferences
    """
    Snapshots represent the state of an aggregate at a particular
    version.

    Constructor arguments:

    :param UUID originator_id: ID of originating aggregate.
    :param int originator_version: version of originating aggregate.
    :param datetime timestamp: date-time of the event
    :param str topic: string that includes a class and its module
    :param dict state: version of originating aggregate.
    """

    topic: str
    state: Dict[str, Any]

    @classmethod
    def take(cls, aggregate: TAggregate) -> "Snapshot[TAggregate]":
        """
        Creates a snapshot of the given :class:`Aggregate` object.
        """
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("_pending_events")
        class_version = getattr(type(aggregate), "class_version", 1)
        if class_version > 1:
            aggregate_state["class_version"] = class_version
        originator_id = aggregate_state.pop("_id")
        originator_version = aggregate_state.pop("_version")
        # noinspection PyArgumentList
        return cls(  # type: ignore
            originator_id=originator_id,
            originator_version=originator_version,
            timestamp=cls.create_timestamp(),
            topic=get_topic(type(aggregate)),
            state=aggregate_state,
        )

    def mutate(self, _: Optional[TAggregate]) -> TAggregate:
        """
        Reconstructs the snapshotted :class:`Aggregate` object.
        """
        cls = resolve_topic(self.topic)
        assert issubclass(cls, Aggregate)
        aggregate_state = dict(self.state)
        from_version = aggregate_state.pop("class_version", 1)
        class_version = getattr(cls, "class_version", 1)
        while from_version < class_version:
            upcast_name = f"upcast_v{from_version}_v{from_version + 1}"
            upcast = getattr(cls, upcast_name)
            upcast(aggregate_state)
            from_version += 1

        aggregate_state["_id"] = self.originator_id
        aggregate_state["_version"] = self.originator_version
        aggregate_state["_pending_events"] = []
        aggregate: TAggregate = object.__new__(cls)

        aggregate.__dict__.update(aggregate_state)
        return aggregate
