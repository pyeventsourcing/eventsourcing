import inspect
from builtins import property
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from types import FunctionType
from typing import Any, Callable, Dict, Iterable, Optional, Type, Union, cast
from uuid import UUID

from eventsourcing.domain import (
    Aggregate,
    BaseAggregate,
    MetaAggregate,
    TAggregate,
)

original_methods: Dict[Type[BaseAggregate.Event], FunctionType] = {}


def aggregate(
    cls: Any = None, *, is_dataclass: Optional[bool]=None
) -> Union[
    Type[TAggregate], Callable[[Any], Type[TAggregate]]
]:
    """

    :rtype: Union[Type[TAggregate], Callable[[Any], Type[TAggregate]]]
    """
    def wrapper(cls: Any) -> Type[TAggregate]:  # type: ignore
        if is_dataclass:
            cls = dataclass(cls)
        cls_dict = {k: v for k, v in cls.__dict__.items()}
        cls_dict["__qualname__"] = cls.__qualname__
        return type(DecoratedAggregate)(cls.__name__, (cls,), cls_dict)

    if cls:
        assert is_dataclass is None
        return wrapper(cls)
    else:
        return wrapper


class EventDecorator:
    def __init__(self, arg: Union[FunctionType, str]):
        self.is_property_setter = False
        self.propery_attribute_name: Optional[str] = None
        self.is_decorating_a_property = False
        self.decorated_property: Optional[property] = None
        self.original_method: Optional[FunctionType] = None
        # Initialising an instance.
        if isinstance(arg, str):
            # Decorator used with an explicit name.
            self.initialise_from_explicit_name(event_cls_name=arg)
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

    def initialise_from_explicit_name(self, event_cls_name: str) -> None:
        self.is_name_inferred_from_method = False
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
            return self
        elif self.is_property_setter:
            # Called by a decorating property (as its fset) so trigger an event.
            assert self.propery_attribute_name
            assert len(args) == 2
            assert len(kwargs) == 0
            assert isinstance(args[0], BaseAggregate)
            kwargs = {self.propery_attribute_name: args[1]}
            bound = BoundEvent(self, args[0])
            bound.trigger(**kwargs)
        else:
            raise ValueError("Unsupported usage: event object was called directly")


event = EventDecorator


def _check_no_variable_params(method: FunctionType) -> None:
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
    method: FunctionType, args: Iterable[Any], kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    assert method
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

    for name in kwargs:
        if name not in required_keyword_only and name not in positional_names:
            raise TypeError(
                f"{method.__name__}() got an unexpected keyword argument '{name}'"
            )

    counter = 0
    if len(args) > len(positional_names):
        msg = (
            f"{method.__name__}() takes {len(positional_names) + 1} positional "
            f"argument{'' if len(positional_names) + 1 == 1 else 's'} "
            f"but {len(args) + 1} were given"
        )
        raise TypeError(msg)

    required_positional_not_in_kwargs = [
        n for n in required_positional if n not in kwargs
    ]
    num_missing = len(required_positional_not_in_kwargs) - len(args)
    if num_missing > 0:
        missing_names = [
            f"'{name}'" for name in required_positional_not_in_kwargs[len(args) :]
        ]
        msg = (
            f"{method.__name__}() missing {num_missing} required positional "
            f"argument{'' if num_missing == 1 else 's'}: "
        )
        msg += missing_names[0]
        if len(missing_names) == 2:
            msg += f" and {missing_names[1]}"
        elif len(missing_names) > 2:
            msg += ", " + ", ".join(missing_names[1:-1])
            msg += f", and {missing_names[-1]}"
        raise TypeError(msg)

    for name in positional_names:
        if counter + 1 > len(args):
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
        msg += missing_names[0]
        if len(missing_names) == 2:
            msg += f" and {missing_names[1]}"
        elif len(missing_names) > 2:
            msg += ", " + ", ".join(missing_names[1:-1])
            msg += f", and {missing_names[-1]}"

        raise TypeError(msg)

    for name, value in keyword_defaults.items():
        if name not in copy_kwargs:
            copy_kwargs[name] = value
    return copy_kwargs


class BoundEvent:
    """
    Wraps an EventDecorator instance when attribute is accessed
    on an aggregate so that the aggregate methods can be accessed.
    """

    def __init__(self, event: EventDecorator, aggregate: TAggregate):
        self.event = event
        self.aggregate = aggregate

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        method = self.event.original_method
        assert method
        kwargs = _coerce_args_to_kwargs(method, args, kwargs)
        event_cls = getattr(self.aggregate, self.event.event_cls_name)
        self.aggregate._trigger_event(event_cls, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.trigger(*args, **kwargs)


class MetaDecoratedAggregate(MetaAggregate):
    def __new__(
        cls, cls_name: str, bases: tuple, cls_dict: Dict[str, Any]
    ) -> "MetaDecoratedAggregate":
        if cls_name == "DecoratedAggregate":
            aggregate_class = MetaAggregate.__new__(cls, cls_name, bases, cls_dict)
            return cast(MetaDecoratedAggregate, aggregate_class)
        else:
            if "__init__" in cls_dict:
                cls_dict["_original_init_method"] = cls_dict.pop("__init__")
                # Avoid inherits from DeclarativeBase...
                if not issubclass(bases[0], DecoratedAggregate):
                    del bases[0].__init__
                # else:
                #     raise Exception("Blah")
            else:
                cls_dict["_original_init_method"] = None

            bases = bases + (Initialiser,)
            aggregate_class = super().__new__(cls, cls_name, bases, cls_dict)
            return cast(MetaDecoratedAggregate, aggregate_class)

    def __init__(self, cls_name: str, bases: tuple, cls_dict: Dict[str, Any]):
        super().__init__(cls_name, bases, cls_dict)
        if cls_name == "DecoratedAggregate":
            return

        original_init_method = cls_dict["_original_init_method"]

        # Prepare the "created" event class.
        for cls_attr in tuple(cls_dict.values()):
            if isinstance(cls_attr, type) and issubclass(
                cls_attr, BaseAggregate.Created
            ):
                # Found a "created" class on the aggregate.
                self._created_cls = cls_attr
                break
        else:
            created_cls_annotations = {}
            if original_init_method:
                _check_no_variable_params(original_init_method)
                method_signature = inspect.signature(original_init_method)
                for param_name in method_signature.parameters:
                    if param_name == "self":
                        continue
                    created_cls_annotations[param_name] = "typing.Any"

            created_cls_name = "Created"
            created_cls_dict = {
                "__annotations__": created_cls_annotations,
                "__qualname__": ".".join([self.__qualname__, created_cls_name]),
                "__module__": self.__qualname__,
            }

            # Define the created class.
            created_cls = type(
                created_cls_name, (BaseAggregate.Created,), created_cls_dict
            )
            # Make it into a frozen dataclass.
            created_cls = dataclass(frozen=True)(created_cls)
            # Put it in the aggregate class dict.
            cls_dict[created_cls_name] = created_cls
            self._created_cls = created_cls

        # Prepare the __init__ method.
        self._original_init_method = original_init_method

        # Prepare the subsequent event classes.
        for attribute in tuple(cls_dict.values()):

            # Watch out for @property that sits over an @event.
            if isinstance(attribute, property) and isinstance(
                attribute.fset, EventDecorator
            ):
                attribute = attribute.fset
                if attribute.is_name_inferred_from_method:
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
                        attribute.propery_attribute_name = param_name
                    annotations[param_name] = "typing.Any"  # Todo: Improve this?

                event_cls_name = attribute.event_cls_name
                event_cls_qualname = ".".join([self.__qualname__, event_cls_name])
                event_cls_dict = {
                    "__annotations__": annotations,
                    "__module__": self.__module__,
                    "__qualname__": event_cls_qualname,
                }

                event_cls = type(event_cls_name, (DecoratedEvent,), event_cls_dict)
                event_cls = dataclass(frozen=True)(event_cls)

                original_methods[event_cls] = original_method
                cls_dict[event_cls_name] = event_cls
                setattr(self, event_cls_name, event_cls)

    def __call__(self, *args: Any, **kwargs: Any) -> TAggregate:
        if self._original_init_method is not None:
            kwargs = _coerce_args_to_kwargs(self._original_init_method, args, kwargs)
        else:
            if args or kwargs:
                raise TypeError(f"{self.__name__}() takes no args")
        aggregate: TAggregate = self._create(
            event_class=self._created_cls,
            # id=self.create_id(**kwargs),
            **kwargs,
        )
        return aggregate


class DecoratedEvent(BaseAggregate.Event):
    def apply(self, aggregate: TAggregate) -> None:
        """
        Applies event to aggregate by calling
        method decorated by @event.
        """
        event_obj_dict = copy(self.__dict__)
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


class DecoratedAggregate(metaclass=MetaDecoratedAggregate):
    id: UUID
    version: int
    created_on: datetime
    modified_on: datetime


class Initialiser(Aggregate):
    _original_init_method: Optional[FunctionType]

    def __init__(self, **kwargs: Any) -> None:
        base_kwargs = {}
        base_kwargs["id"] = kwargs.pop("id")
        base_kwargs["version"] = kwargs.pop("version")
        base_kwargs["timestamp"] = kwargs.pop("timestamp")
        super().__init__(**base_kwargs)
        if self._original_init_method:
            self._original_init_method(**kwargs)

    def __getattribute__(self, item: str) -> Any:
        attr = super().__getattribute__(item)
        if isinstance(attr, EventDecorator):
            if attr.is_decorating_a_property:
                assert attr.decorated_property
                assert attr.decorated_property.fget
                return attr.decorated_property.fget(self)  # type: ignore
            else:
                return BoundEvent(attr, self)
        else:
            return attr

    def __setattr__(self, name: str, value: Any) -> Any:
        try:
            attr = super().__getattribute__(name)
        except AttributeError:
            # Set new attribute.
            super().__setattr__(name, value)
        else:
            if isinstance(attr, EventDecorator):
                # Set decorated property.
                b = BoundEvent(attr, self)
                kwargs = {name: value}
                b.trigger(**kwargs)

            else:
                # Set existing attribute.
                super().__setattr__(name, value)
