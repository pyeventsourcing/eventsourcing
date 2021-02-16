import inspect
from builtins import property
from copy import copy
from dataclasses import dataclass
from types import FunctionType
from typing import Any, Dict, Iterable, Optional, Type, Union, cast
from uuid import uuid4

from eventsourcing.domain import Aggregate

original_methods: Dict[Type[Aggregate.Event], FunctionType] = {}


def aggregate(original_cls: Any) -> Type[Aggregate]:

    # Prepare the "created" event class.
    created_cls_annotations = {}
    try:
        cls_init_method = original_cls.__dict__["__init__"]
    except KeyError:
        has_init_method = False
    else:
        has_init_method = True
        check_no_variable_params(cls_init_method)
        method_signature = inspect.signature(cls_init_method)
        for param_name in method_signature.parameters:
            if param_name == "self":
                continue
            created_cls_annotations[param_name] = "typing.Any"

    created_cls_dict = {
        "__annotations__": created_cls_annotations,
        "__qualname__": ".".join([original_cls.__qualname__, "Created"]),
        "__module__": original_cls.__module__,
    }

    created_cls = cast(
        Type[Aggregate.Created],
        type("Created", (Aggregate.Created,), created_cls_dict),
    )

    created_cls = dataclass(frozen=True)(created_cls)

    # Prepare the aggregate class.
    # Todo: Put this in a metaclass... (then don't need *args in __init__ and it
    #  won't be called twice).
    def __new__(cls: Type[Aggregate], *args: Any, **kwargs: Any) -> Aggregate:
        # if original_cls.__init__ != object.__init__:
        if has_init_method:
            kwargs = coerce_args_to_kwargs(original_cls.__init__, args, kwargs)
        return cls._create(event_class=created_cls, id=uuid4(), **kwargs)

    def __init__(self: Aggregate, *args: Any, **kwargs: Any) -> None:
        if "id" not in kwargs:
            return  # Python calls me again...
        base_kwargs = {}
        base_kwargs["id"] = kwargs.pop("id")
        base_kwargs["version"] = kwargs.pop("version")
        base_kwargs["timestamp"] = kwargs.pop("timestamp")
        Aggregate.__init__(self, **base_kwargs)
        if has_init_method:
            original_cls.__init__(self, **kwargs)

    def getattribute(self: Aggregate, item: str) -> Any:
        attr = super(Aggregate, self).__getattribute__(item)
        if isinstance(attr, event):
            if attr.is_decorating_a_property:
                assert attr.decorated_property
                assert attr.decorated_property.fget
                return attr.decorated_property.fget(self)  # type: ignore
            else:
                return bound_event(attr, self)
        else:
            return attr

    def __setattr__(self: Aggregate, name: str, value: Any) -> Any:
        try:
            attr = super(Aggregate, self).__getattribute__(name)
        except AttributeError:
            # Set new attribute.
            super(Aggregate, self).__setattr__(name, value)
        else:
            if isinstance(attr, event):
                # Set property.
                b = bound_event(attr, self)
                kwargs = {name: value}
                b.trigger(**kwargs)

            else:
                # Set existing attribute.
                super(Aggregate, self).__setattr__(name, value)

    aggregate_cls_dict = {
        "__module__": original_cls.__module__,
        "__qualname__": original_cls.__qualname__,
        "__doc__": original_cls.__doc__,
        "__new__": __new__,
        "__init__": __init__,
        "__getattribute__": getattribute,
        "__setattr__": __setattr__,
        "Created": created_cls,
    }
    aggregate_cls = cast(
        Aggregate,
        type(original_cls.__name__, (original_cls, Aggregate), aggregate_cls_dict),
    )

    for name in dir(original_cls):
        attribute = getattr(original_cls, name)

        if isinstance(attribute, property) and isinstance(attribute.fset, event):
            attribute = attribute.fset
            if attribute.is_name_inferred_from_method:
                method_name = attribute.original_method.__name__
                raise ValueError(
                    f"@event on {method_name}() property setter requires event class "
                    f"name"
                )
            # Attribute is a property decorating an event decorator.
            attribute.is_property_setter = True

        # Attribute is an event decorator.
        if isinstance(attribute, event):
            # Prepare the subsequent aggregate events.
            original_method = attribute.original_method
            assert isinstance(original_method, FunctionType)

            event_cls_name = attribute.event_cls_name
            event_cls_qualname = ".".join([original_cls.__qualname__, event_cls_name])

            assert isinstance(original_method, FunctionType)

            method_signature = inspect.signature(original_method)
            annotations = {}
            for param_name in method_signature.parameters:
                if param_name == "self":
                    continue
                elif attribute.is_property_setter:
                    assert len(method_signature.parameters) == 2
                    attribute.propery_attribute_name = param_name
                    annotations[param_name] = "typing.Any"

                else:
                    annotations[param_name] = "typing.Any"

            event_cls_dict = {
                "__annotations__": annotations,
                "__module__": original_cls.__module__,
                "__qualname__": event_cls_qualname,
                "apply": apply,
            }

            event_cls: Type[Aggregate.Event] = cast(
                Type[Aggregate.Event],
                type(event_cls_name, (Aggregate.Event,), event_cls_dict),
            )

            event_cls = dataclass(frozen=True)(event_cls)

            original_methods[event_cls] = original_method
            setattr(aggregate_cls, event_cls_name, event_cls)

    return cast(Type[Aggregate], aggregate_cls)


# Prepare the aggregate event classes.
def apply(self: Aggregate.Event, aggregate: Aggregate) -> None:
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


class event:
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
            raise TypeError(
                f"Unsupported usage: {type(arg)} is not a str or a FunctionType"
            )

    def initialise_from_decorated_method(self, original_method: FunctionType) -> None:
        self.is_name_inferred_from_method = True
        self.event_cls_name = "".join(
            [s.capitalize() for s in original_method.__name__.split("_")]
        )
        self.original_method = original_method
        check_no_variable_params(self.original_method)

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
                check_no_variable_params(self.original_method)
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
                check_no_variable_params(self.original_method)
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
            assert isinstance(args[0], Aggregate)
            kwargs = {self.propery_attribute_name: args[1]}
            bound = bound_event(self, args[0])
            bound.trigger(**kwargs)
        else:
            raise ValueError("Unsupported usage: event object was called directly")


def check_no_variable_params(method: FunctionType) -> None:
    for param in inspect.signature(method).parameters.values():
        if param.kind is param.VAR_POSITIONAL:
            raise TypeError("variable positional parameters not supported")
            # Todo: Support VAR_POSITIONAL?
            # annotations["__star_args__"] = "typing.Any"

        elif param.kind is param.VAR_KEYWORD:
            # Todo: Support VAR_KEYWORD?
            # annotations["__star_kwargs__"] = "typing.Any"
            raise TypeError("variable keyword parameters not supported")


def coerce_args_to_kwargs(
    method: FunctionType, args: Iterable[Any], kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    assert method
    method_signature = inspect.signature(method)
    kwargs = dict(kwargs)
    args = tuple(args)
    positional_names = []
    keyword_defaults = {}
    required_positional = []
    required_keyword_only = []
    missing_keyword_only_arguments = []

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

    for name in required_keyword_only:
        if name not in kwargs:
            missing_keyword_only_arguments.append(name)

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
            kwargs[name] = args[counter]
            counter += 1
        else:
            raise TypeError(
                f"{method.__name__}() got multiple values for argument '{name}'"
            )

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
        if name not in kwargs:
            kwargs[name] = value
    return kwargs


class bound_event:
    def __init__(self, event: event, aggregate: Aggregate):
        self.event = event
        self.aggregate = aggregate

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        method = self.event.original_method
        assert method
        kwargs = coerce_args_to_kwargs(method, args, kwargs)
        event_cls = getattr(self.aggregate, self.event.event_cls_name)
        self.aggregate._trigger_event(event_cls, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.trigger(*args, **kwargs)


# T = TypeVar("T", bound="DeclarativeAggregate")
#
#
#
# class MetaDeclarativeAggregate(MetaAggregate):
#     def __new__(cls, *args: Any, **kwargs: Any) -> Type[T]:
#         aggregate_class = type.__new__(cls, *args, **kwargs)
#
#         # Prepare the "created" event class.
#         created_cls_annotations = {}
#         try:
#             cls_init_method = aggregate_class.__dict__["__init__"]
#         except KeyError:
#             has_init_method = False
#         else:
#             has_init_method = True
#             # check_no_variable_params(cls_init_method)
#             method_signature = inspect.signature(cls_init_method)
#             for param_name, param in method_signature.parameters.items():
#                 if param_name == "self":
#                     continue
#                 elif param.kind is param.VAR_POSITIONAL:
#                     raise TypeError("variable positional parameters not supported")
#                 elif param.kind is param.VAR_KEYWORD:
#                     continue  # Assuming these are the base aggregate init kwargs.
#
#                 created_cls_annotations[param_name] = "typing.Any"
#
#         created_cls_dict = {
#             "__annotations__": created_cls_annotations,
#             "__qualname__": ".".join([aggregate_class.__qualname__, "Created"]),
#             "__module__": aggregate_class.__module__,
#         }
#
#         created_cls = type("Created", (BaseAggregate.Created,), created_cls_dict)
#
#         created_cls = dataclass(frozen=True)(created_cls)
#         aggregate_class.Created = created_cls
#
#         for name in dir(aggregate_class):
#             attribute = getattr(aggregate_class, name)
#
#             if isinstance(attribute, property) and isinstance(attribute.fset, event):
#                 attribute = attribute.fset
#                 if attribute.is_name_inferred_from_method:
#                     raise ValueError(
#                         "Can't decorate property without explicit event name")
#                 # Attribute is a property decorating an event decorator.
#                 attribute.is_property_setter = True
#
#             # Attribute is an event decorator.
#             if isinstance(attribute, event):
#                 # Prepare the subsequent aggregate events.
#                 original_method = attribute.original_method
#                 assert isinstance(original_method, FunctionType)
#
#                 event_cls_name = attribute.event_cls_name
#                 event_cls_qualname = ".".join(
#                     [aggregate_class.__qualname__, event_cls_name])
#
#                 assert isinstance(original_method, FunctionType)
#
#                 method_signature = inspect.signature(original_method)
#                 annotations = {}
#                 for param_name in method_signature.parameters:
#                     if param_name == "self":
#                         continue
#                     elif attribute.is_property_setter:
#                         assert len(method_signature.parameters) == 2
#                         attribute.propery_attribute_name = param_name
#                         annotations[param_name] = "typing.Any"
#
#                     else:
#                         annotations[param_name] = "typing.Any"
#
#                 event_cls_dict = {
#                     "__annotations__": annotations,
#                     "__module__": aggregate_class.__module__,
#                     "__qualname__": event_cls_qualname,
#                     "apply": apply,
#                 }
#
#                 event_cls: Type[Aggregate.Event] = cast(
#                     Type[Aggregate.Event],
#                     type(event_cls_name, (Aggregate.Event,), event_cls_dict),
#                 )
#
#                 event_cls = dataclass(frozen=True)(event_cls)
#
#                 original_methods[event_cls] = original_method
#                 setattr(aggregate_class, event_cls_name, event_cls)
#
#         return aggregate_class
#
#     def __call__(self: Type[T], *args, **kwargs) -> T:
#         return self.__new__(self)
#
#
# class DeclarativeAggregate(BaseAggregate, metaclass=MetaDeclarativeAggregate):
#     def __new__(cls: Type[T], *args, **kwargs) -> T:
#         kwargs = coerce_args_to_kwargs(cls.__init__, args, kwargs)
#         return cls._create(event_class=cls.Created, id=uuid4(), **kwargs)
#
#     def __getattribute__(self, item: str) -> Any:
#         attr = super().__getattribute__(item)
#         if isinstance(attr, event):
#             if attr.is_decorating_a_property:
#                 assert attr.decorated_property
#                 assert attr.decorated_property.fget
#                 return attr.decorated_property.fget(self)  # type: ignore
#             else:
#                 return bound_event(attr, self)
#         else:
#             return attr
