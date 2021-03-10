import inspect
import os
from dataclasses import dataclass
from datetime import datetime, tzinfo
from types import FunctionType, WrapperDescriptorType
from typing import (
    Any,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID, uuid4

from eventsourcing.utils import get_topic, resolve_topic

TZINFO: tzinfo = resolve_topic(os.getenv("TZINFO_TOPIC", "datetime:timezone.utc"))

# noinspection PyTypeChecker
TAggregate = TypeVar("TAggregate", bound="Aggregate")


class MetaDomainEvent(type):
    def __new__(mcs, name: str, bases: tuple, cls_dict: dict) -> "MetaDomainEvent":
        event_cls = type.__new__(mcs, name, bases, cls_dict)
        event_cls = dataclass(frozen=True)(event_cls)
        return cast(MetaDomainEvent, event_cls)

    def __init__(cls, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)


class DomainEvent(metaclass=MetaDomainEvent):
    # noinspection PyUnresolvedReferences
    """
    Base class for domain events, such as aggregate :class:`AggregateEvent`
    and aggregate :class:`Snapshot`.

    Constructor arguments:

    :param UUID originator_id: ID of originating aggregate.
    :param int originator_version: version of originating aggregate.
    :param datetime timestamp: date-time of the event
    """

    originator_id: UUID
    originator_version: int
    timestamp: datetime


class AggregateEvent(DomainEvent, Generic[TAggregate]):
    # noinspection PyUnresolvedReferences
    """
    Base class for aggregate events. Subclasses will model
    decisions made by the domain model aggregates.

    Constructor arguments:

    :param UUID originator_id: ID of originating aggregate.
    :param int originator_version: version of originating aggregate.
    :param datetime timestamp: date-time of the event
    """

    def mutate(self, obj: Optional[TAggregate]) -> Optional[TAggregate]:
        """
        Changes the state of the aggregate
        according to domain event attributes.
        """
        # Check event is next in its sequence.
        # Use counting to follow the sequence.
        # assert isinstance(obj, Aggregate), (type(obj), self)
        assert obj is not None
        next_version = obj.version + 1
        if self.originator_version != next_version:
            raise VersionError(self.originator_version, next_version)
        # Update the aggregate version.
        obj.version = next_version
        # Update the modified time.
        obj.modified_on = self.timestamp
        self.apply(obj)
        return obj

    # noinspection PyShadowingNames
    def apply(self, aggregate: TAggregate) -> None:
        """
        Applies the domain event to the aggregate.
        """


class AggregateCreated(AggregateEvent["Aggregate"]):
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

    def mutate(self, obj: Optional[TAggregate]) -> TAggregate:
        """
        Constructs aggregate instance defined
        by domain event object attributes.
        """
        assert obj is None
        # Copy the event attributes.
        kwargs = self.__dict__.copy()
        # Resolve originator topic.
        aggregate_class: Type[TAggregate] = resolve_topic(
            kwargs.pop("originator_topic")
        )

        # Construct and return aggregate object.
        agg: TAggregate = aggregate_class.__new__(aggregate_class)
        # Separate the base class keywords arguments.
        base_kwargs = {
            "id": kwargs.pop("originator_id"),
            "version": kwargs.pop("originator_version"),
            "timestamp": kwargs.pop("timestamp"),
        }
        Aggregate.__base_init__(agg, **base_kwargs)
        # noinspection PyArgumentList
        agg.__init__(**kwargs)  # type: ignore
        return agg


class EventDecorator:
    def __init__(self, arg: Union[FunctionType, str, Type[AggregateEvent]]):
        self.is_name_inferred_from_method = False
        self.given_event_cls: Optional[Type[AggregateEvent]] = None
        self.event_cls_name: Optional[str] = None
        self.is_property_setter = False
        self.property_attribute_name: Optional[str] = None
        self.is_decorating_a_property = False
        self.decorated_property: Optional[property] = None
        self.original_method: Optional[FunctionType] = None
        # Initialising an instance.
        if isinstance(arg, str):
            # Decorator used with an explicit name.
            self.initialise_from_explicit_name(event_cls_name=arg)
        elif isinstance(arg, type) and issubclass(arg, AggregateEvent):
            self.initialise_from_event_cls(event_cls=arg)
        elif isinstance(arg, FunctionType):
            # Decorator used without explicit name.
            self.initialise_from_decorated_method(original_method=arg)
        elif isinstance(arg, property):
            method_name = arg.fset.__name__
            raise TypeError(
                f"@event on {method_name}() property setter requires event class name"
            )
        elif isinstance(arg, staticmethod):
            raise TypeError(
                f"{arg.__func__.__name__}() staticmethod can't be "
                f"used to update aggregate state"
            )
        elif isinstance(arg, classmethod):
            raise TypeError(
                f"{arg.__func__.__name__}() classmethod can't be "
                f"used to update aggregate state"
            )
        else:
            raise TypeError(f"Unsupported usage: {type(arg)} is not a str or function")

    def initialise_from_decorated_method(self, original_method: FunctionType) -> None:
        self.is_name_inferred_from_method = True
        self.event_cls_name = "".join(
            [s.capitalize() for s in original_method.__name__.split("_")]
        )
        self.original_method = original_method
        _check_no_variable_params(self.original_method)

    def initialise_from_event_cls(self, event_cls: Type[AggregateEvent]) -> None:
        self.given_event_cls = event_cls

    def initialise_from_explicit_name(self, event_cls_name: str) -> None:
        self.event_cls_name = event_cls_name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Calling an instance.
        if self.original_method is None:
            # Decorator used with name, still decorating...
            assert len(kwargs) == 0, "Unsupported usage"
            assert len(args) == 1, "Unsupported usage"
            arg = args[0]
            # assert isinstance(args[0], FunctionType), args[0]
            if isinstance(arg, FunctionType):
                # Decorating a function.
                self.original_method = arg
                _check_no_variable_params(self.original_method)
            elif isinstance(arg, property):
                # Decorating a property.
                self.is_decorating_a_property = True
                self.decorated_property = arg
                if arg.fset is None:
                    method_name = arg.fget.__name__
                    raise TypeError(
                        f"@event can't decorate {method_name}() property getter"
                    )
                assert isinstance(arg.fset, FunctionType)
                self.original_method = arg.fset
                assert self.original_method
                _check_no_variable_params(self.original_method)
            else:
                raise ValueError(
                    f"Unsupported usage: {type(arg)} is not a str or a FunctionType"
                )
            if self.given_event_cls:
                if self.given_event_cls in original_methods:
                    name = self.given_event_cls.__name__
                    raise TypeError(
                        f"{name} event class used in more than one decorator"
                    )

                # Set decorated event apply() method on given event class.
                if "apply" in self.given_event_cls.__dict__:
                    name = self.given_event_cls.__name__
                    raise TypeError(f"{name} event class has unexpected apply() method")
                # self.given_event_cls.apply = DecoratedEvent.apply  # type: ignore
                setattr(  # noqa: B010
                    self.given_event_cls, "apply", DecoratedEvent.apply
                )
                # Register the decorated method under the given event class.
                original_methods[self.given_event_cls] = self.original_method
            return self
        else:
            assert self.is_property_setter
            # Called by a decorating property (as its fset) so trigger an event.
            assert self.property_attribute_name
            assert len(args) == 2
            assert len(kwargs) == 0
            assert isinstance(args[0], Aggregate)
            kwargs = {self.property_attribute_name: args[1]}
            bound = BoundEvent(self, args[0])
            bound.trigger(**kwargs)

    def __get__(self, instance: TAggregate, owner: "MetaAggregate") -> "BoundEvent":
        if self.is_decorating_a_property:
            assert self.decorated_property
            return self.decorated_property.__get__(instance, owner)
        else:
            if instance is None:
                raise TypeError("Unsupported usage: event object used without instance")
            else:
                return BoundEvent(self, instance)

    def __set__(self, instance: TAggregate, value: Any) -> None:
        assert self.is_decorating_a_property
        # Set decorated property.
        b = BoundEvent(self, instance)
        assert self.original_method
        name = self.original_method.__name__
        kwargs = {name: value}
        b.trigger(**kwargs)


class BoundEvent:
    """
    Wraps an EventDecorator instance when attribute is accessed
    on an aggregate so that the aggregate methods can be accessed.
    """

    # noinspection PyShadowingNames
    def __init__(self, event_decorator: EventDecorator, aggregate: TAggregate):
        """

        :param event_decorator EventDecorator:
        :param aggregate Aggregate:
        """
        self.event_decorator = event_decorator
        self.aggregate = aggregate

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        # This assert isinstance avoids PyCharm thinking that
        # self.event_decorator is a BoundEvent. No idea why!
        assert isinstance(self.event_decorator, EventDecorator)
        assert self.event_decorator.original_method
        kwargs = _coerce_args_to_kwargs(
            self.event_decorator.original_method, args, kwargs
        )
        if self.event_decorator.given_event_cls:
            event_cls = self.event_decorator.given_event_cls
        else:
            assert self.event_decorator.event_cls_name
            event_cls = getattr(self.aggregate, self.event_decorator.event_cls_name)
        self.aggregate.trigger_event(event_cls, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.trigger(*args, **kwargs)


original_methods: Dict[MetaDomainEvent, FunctionType] = {}


class DecoratedEvent(AggregateEvent):
    def apply(self, aggregate: TAggregate) -> None:
        """
        Applies event to aggregate by calling
        method decorated by @event.
        """
        event_obj_dict = dict(self.__dict__)
        event_obj_dict.pop("originator_id")
        event_obj_dict.pop("originator_version")
        event_obj_dict.pop("timestamp")
        original_method = original_methods[type(self)]
        method_signature = inspect.signature(original_method)
        # args = []
        # for name, param in method_signature.parameters.items():
        for name in method_signature.parameters:
            if name == "self":
                continue
        #     if param.kind == param.POSITIONAL_ONLY:
        #         args.append(event_obj_dict.pop(name))
        # original_method(aggregate, *args, **event_obj_dict)
        original_method(aggregate, **event_obj_dict)


triggers = event = EventDecorator


TDomainEvent = TypeVar("TDomainEvent", bound=DomainEvent)
TAggregateEvent = TypeVar("TAggregateEvent", bound=AggregateEvent)
TAggregateCreated = TypeVar("TAggregateCreated", bound=AggregateCreated)


def _check_no_variable_params(
    method: Union[FunctionType, WrapperDescriptorType]
) -> None:
    assert isinstance(method, (FunctionType, WrapperDescriptorType))
    for param in inspect.signature(method).parameters.values():
        if param.kind is param.VAR_POSITIONAL:
            raise TypeError("variable positional parameters not supported")
            # Todo: Support VAR_POSITIONAL?
            # annotations["__star_args__"] = "typing.Any"

        elif param.kind is param.VAR_KEYWORD:
            # Todo: Support VAR_KEYWORD?
            # annotations["__star_kwargs__"] = "typing.Any"
            raise TypeError("variable keyword parameters not supported")


def _coerce_args_to_kwargs(
    method: Union[FunctionType, WrapperDescriptorType],
    args: Iterable[Any],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    assert isinstance(method, (FunctionType, WrapperDescriptorType))
    method_signature = inspect.signature(method)
    copy_kwargs = dict(kwargs)
    args = tuple(args)
    positional_names = []
    keyword_defaults = {}
    required_positional = []
    required_keyword_only = []

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

    for name in kwargs:
        if name not in required_keyword_only and name not in positional_names:
            raise TypeError(
                f"{method.__name__}() got an unexpected keyword argument '{name}'"
            )

    counter = 0
    len_args = len(args)
    if len_args > len(positional_names):
        msg = (
            f"{method.__name__}() takes {len(positional_names) + 1} positional "
            f"argument{'' if len(positional_names) + 1 == 1 else 's'} "
            f"but {len_args + 1} were given"
        )
        raise TypeError(msg)

    required_positional_not_in_kwargs = [
        n for n in required_positional if n not in kwargs
    ]
    num_missing = len(required_positional_not_in_kwargs) - len_args
    if num_missing > 0:
        missing_names = [
            f"'{name}'" for name in required_positional_not_in_kwargs[len_args:]
        ]
        msg = (
            f"{method.__name__}() missing {num_missing} required positional "
            f"argument{'' if num_missing == 1 else 's'}: "
        )
        raise_missing_names_type_error(missing_names, msg)

    for name in positional_names:
        if counter + 1 > len_args:
            break
        if name not in kwargs:
            copy_kwargs[name] = args[counter]
            counter += 1
        else:
            raise TypeError(
                f"{method.__name__}() got multiple values for argument '{name}'"
            )

    missing_keyword_only_arguments = []
    for name in required_keyword_only:
        if name not in kwargs:
            missing_keyword_only_arguments.append(name)

    if missing_keyword_only_arguments:
        missing_names = [f"'{name}'" for name in missing_keyword_only_arguments]
        msg = (
            f"{method.__name__}() missing {len(missing_names)} "
            f"required keyword-only argument"
            f"{'' if len(missing_names) == 1 else 's'}: "
        )
        raise_missing_names_type_error(missing_names, msg)

    for name, value in keyword_defaults.items():
        if name not in copy_kwargs:
            copy_kwargs[name] = value
    return copy_kwargs


def raise_missing_names_type_error(missing_names: List[str], msg: str) -> None:
    msg += missing_names[0]
    if len(missing_names) == 2:
        msg += f" and {missing_names[1]}"
    elif len(missing_names) > 2:
        msg += ", " + ", ".join(missing_names[1:-1])
        msg += f", and {missing_names[-1]}"
    raise TypeError(msg)


class MetaAggregate(type):
    def __new__(
        mcs, cls_name: str, cls_bases: Tuple, cls_dict: Dict
    ) -> "MetaAggregate":
        event_cls = type.__new__(mcs, cls_name, cls_bases, cls_dict)
        # if cls_bases:
        #     event_cls = dataclass(event_cls)
        return cast(MetaAggregate, event_cls)

    def __init__(cls, cls_name: str, cls_bases: Tuple, cls_dict: Dict) -> None:
        super().__init__(cls_name, cls_bases, cls_dict)
        created_event_classes = []
        created_event_class = None
        for name, value in tuple(cls.__dict__.items()):
            if isinstance(value, type) and issubclass(value, AggregateCreated):
                created_event_classes.append(value)
            if name == "_created_event_class":
                created_event_class = value
        if created_event_class is None:
            if len(created_event_classes) == 0:
                # Define a "created" event for this class.
                created_cls_annotations = {}
                # noinspection PyTypeChecker
                init_method: WrapperDescriptorType = cls.__init__  # type: ignore
                if init_method is not object.__init__:
                    _check_no_variable_params(init_method)
                    method_signature = inspect.signature(init_method)
                    for param_name in method_signature.parameters:
                        if param_name == "self":
                            continue
                        created_cls_annotations[param_name] = "typing.Any"

                created_event_class = type(
                    "Created",
                    (AggregateCreated,),
                    {
                        "__annotations__": created_cls_annotations,
                        "__module__": cls.__module__,
                        "__qualname__": ".".join([cls.__qualname__, "Created"]),
                    },
                )
                cls.Created = created_event_class
                # setattr(self, "Created", created_event_class)
                created_event_class = created_event_class
            elif len(created_event_classes) == 1:
                created_event_class = created_event_classes[0]

            cls._created_event_class = created_event_class

        # Prepare the subsequent event classes.
        for attribute in tuple(cls_dict.values()):

            # Watch out for @property that sits over an @event.
            if isinstance(attribute, property) and isinstance(
                attribute.fset, EventDecorator
            ):
                attribute = attribute.fset
                if attribute.is_name_inferred_from_method:
                    # We don't want name inferred from property (not past participle).
                    method_name = attribute.original_method.__name__
                    raise TypeError(
                        f"@event under {method_name}() property setter requires event "
                        f"class name"
                    )
                # Attribute is a property decorating an event decorator.
                attribute.is_property_setter = True

            # Attribute is an event decorator.
            if isinstance(attribute, EventDecorator):
                # Prepare the subsequent aggregate events.
                original_method = attribute.original_method
                assert isinstance(original_method, FunctionType)

                method_signature = inspect.signature(original_method)
                annotations = {}
                for param_name in method_signature.parameters:
                    if param_name == "self":
                        continue
                    elif attribute.is_property_setter:
                        assert len(method_signature.parameters) == 2
                        attribute.property_attribute_name = param_name
                    annotations[param_name] = "typing.Any"  # Todo: Improve this?

                if not attribute.given_event_cls:
                    assert attribute.event_cls_name
                    event_cls_name = attribute.event_cls_name

                    # Check event class isn't already defined.
                    if event_cls_name in cls_dict:
                        raise TypeError(
                            f"{event_cls_name} event already defined on {cls_name}"
                        )

                    event_cls_qualname = ".".join([cls.__qualname__, event_cls_name])
                    event_cls_dict = {
                        "__annotations__": annotations,
                        "__module__": cls.__module__,
                        "__qualname__": event_cls_qualname,
                    }
                    event_cls = MetaDomainEvent(
                        event_cls_name, (DecoratedEvent,), event_cls_dict
                    )
                    original_methods[event_cls] = original_method
                    cls_dict[event_cls_name] = event_cls
                    setattr(cls, event_cls_name, event_cls)

    def __call__(cls: "MetaAggregate", *args: Any, **kwargs: Any) -> TAggregate:
        object_init = object.__init__
        # noinspection PyTypeChecker
        self_init: WrapperDescriptorType = cls.__init__  # type: ignore
        if self_init is object_init:
            if args or kwargs:
                raise TypeError(f"{cls.__name__}() takes no args")

        kwargs = _coerce_args_to_kwargs(self_init, args, kwargs)

        if cls._created_event_class is None:
            raise TypeError("attribute '_created_event_class' not set on class")
        else:
            new_aggregate: TAggregate = cls._create(
                event_class=cls._created_event_class,
                **kwargs,
            )
            return new_aggregate

    # noinspection PyUnusedLocal
    @staticmethod
    def create_id(**kwargs: Any) -> UUID:
        return uuid4()

    # noinspection PyShadowingBuiltins
    def _create(
        self,
        event_class: Type[TAggregateCreated],
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
        try:
            created_event: TAggregateCreated = event_class(  # type: ignore
                originator_topic=get_topic(self),
                originator_id=id or self.create_id(**kwargs),
                originator_version=1,
                timestamp=datetime.now(tz=TZINFO),
                **kwargs,
            )
        except TypeError as e:
            msg = (
                f"Unable to construct 'aggregate created' "
                f"event with class {event_class.__qualname__} "
                f"and keyword args {kwargs}: {e}"
            )
            raise TypeError(msg)
        # Construct the aggregate object.
        agg: TAggregate = created_event.mutate(None)
        # Append the domain event to pending list.
        agg.pending_events.append(created_event)
        # Return the aggregate.
        return agg


class Aggregate(metaclass=MetaAggregate):
    """
    Base class for aggregate roots.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return object.__new__(cls)

    # noinspection PyShadowingBuiltins
    def __base_init__(self, id: UUID, version: int, timestamp: datetime) -> None:
        """
        Initialises an aggregate object with an :data:`id`, a :data:`version`
        number, and a :data:`timestamp`. The internal :data:`pending_events` list
        is also initialised.
        """
        self._id = id
        self.version = version
        self._created_on = timestamp
        self.modified_on = timestamp
        self._pending_events: List[AggregateEvent] = []

    @property
    def id(self) -> UUID:
        """
        The ID of the aggregate.
        """
        return self._id

    @property
    def created_on(self) -> datetime:
        """
        The date and time when the aggregate was created.
        """
        return self._created_on

    @property
    def pending_events(self) -> List[AggregateEvent]:
        """
        A list of pending events.
        """
        return self._pending_events

    def trigger_event(
        self,
        event_class: Type[TAggregateEvent],
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
        try:
            new_event = event_class(  # type: ignore
                originator_id=self.id,
                originator_version=next_version,
                timestamp=datetime.now(tz=TZINFO),
                **kwargs,
            )
        except TypeError as e:
            raise TypeError(f"Can't construct event {event_class}: {e}")

        # Mutate aggregate with domain event.
        new_event.mutate(self)
        # Append the domain event to pending list.
        self.pending_events.append(new_event)

    def collect_events(self) -> List[AggregateEvent]:
        """
        Collects and returns a list of pending aggregate
        :class:`AggregateEvent` objects.
        """
        collected = []
        while self.pending_events:
            collected.append(self.pending_events.pop(0))
        return collected


def aggregate(cls: Any) -> MetaAggregate:
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
    if issubclass(cls, Aggregate):
        raise TypeError("already an Aggregate")
    return MetaAggregate(cls.__name__, (Aggregate,), dict(cls.__dict__))


class VersionError(Exception):
    """
    Raised when a domain event can't be applied to
    an aggregate due to version mismatch indicating
    the domain event is not the next in the aggregate's
    sequence of events.
    """


class Snapshot(DomainEvent):
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
    state: dict

    # noinspection PyShadowingNames
    @classmethod
    def take(cls, aggregate: TAggregate) -> "Snapshot":
        """
        Creates a snapshot of the given :class:`Aggregate` object.
        """
        aggregate_state = dict(aggregate.__dict__)
        aggregate_state.pop("_pending_events")
        class_version = getattr(type(aggregate), "class_version", 1)
        if class_version > 1:
            aggregate_state["class_version"] = class_version
        originator_id = aggregate_state.pop("_id")
        originator_version = aggregate_state.pop("version")
        # noinspection PyArgumentList
        return cls(  # type: ignore
            originator_id=originator_id,
            originator_version=originator_version,
            timestamp=datetime.now(tz=TZINFO),
            topic=get_topic(type(aggregate)),
            state=aggregate_state,
        )

    def mutate(self, _: None = None) -> TAggregate:
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
        aggregate_state["version"] = self.originator_version
        aggregate_state["_pending_events"] = []
        aggregate = object.__new__(cls)
        aggregate.__dict__.update(aggregate_state)
        return aggregate
