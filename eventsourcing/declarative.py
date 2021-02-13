import inspect
from builtins import property
from copy import copy
from dataclasses import dataclass
from types import FunctionType
from typing import Any, Dict, Type, Union, cast
from uuid import uuid4

from eventsourcing.domain import Aggregate

original_methods: Dict[Type[Aggregate.Event], FunctionType] = {}


def aggregate(original_cls: Type[Any]) -> Type[Aggregate]:

    # Prepare the "created" event class.
    created_cls_annotations = {}
    try:
        cls_init_method = original_cls.__dict__["__init__"]
    except KeyError:
        has_init_method = False
    else:
        has_init_method = True
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
    def __new__(cls: Type[Aggregate], **kwargs: Any) -> Aggregate:
        return cls._create(event_class=created_cls, id=uuid4(), **kwargs)

    def __init__(self: Aggregate, **kwargs: Any) -> None:
        if "id" not in kwargs:
            return  # Python calls me again...
        base_kwargs = {}
        base_kwargs["id"] = kwargs.pop("id")
        base_kwargs["version"] = kwargs.pop("version")
        base_kwargs["timestamp"] = kwargs.pop("timestamp")
        Aggregate.__init__(self, **base_kwargs)
        if has_init_method:
            original_cls.__init__(self, **kwargs)

    def __getattribute__(self, item):
        attr = super(Aggregate, self).__getattribute__(item)
        if isinstance(attr, event):
            return bound_event(attr, self)
        else:
            return attr

    aggregate_cls_dict = {
        "__module__": original_cls.__module__,
        "__qualname__": original_cls.__qualname__,
        "__doc__": original_cls.__doc__,
        "__new__": __new__,
        "__init__": __init__,
        "__getattribute__": __getattribute__,
        "Created": created_cls,
    }
    aggregate_cls = cast(
        Aggregate,
        type(original_cls.__name__, (original_cls, Aggregate), aggregate_cls_dict),
    )

    # Prepare the aggregate event classes.
    def apply(self: Aggregate.Event, aggregate: Aggregate) -> None:
        event_obj_dict = copy(self.__dict__)
        event_obj_dict.pop("originator_id")
        event_obj_dict.pop("originator_version")
        event_obj_dict.pop("timestamp")
        original_methods[type(self)](aggregate, **event_obj_dict)

    for name in dir(original_cls):
        attribute = getattr(original_cls, name)
        if isinstance(attribute, (event, property)):
            if isinstance(attribute, property):
                if isinstance(attribute.fset, event):
                    attribute = attribute.fset
                    attribute.is_property_setter = True
                else:
                    continue

            # Prepare the subsequent aggregate events.
            original_method = attribute.original_method

            event_cls_name = attribute.event_cls_name
            event_cls_qualname = ".".join([original_cls.__qualname__, event_cls_name])

            if isinstance(original_method, property):
                assert original_method.setter
                original_method = original_method.fset
            method_signature = inspect.signature(original_method)
            annotations = {}
            for param_name in method_signature.parameters:
                if param_name == "self":
                    continue
                annotations[param_name] = "typing.Any"
                if attribute.is_property_setter:
                    attribute.propery_attribute_name = param_name
                    assert len(method_signature.parameters) == 2

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
        elif isinstance(attribute, property):
            if attribute.fset:
                raise Exception(inspect.signature(attribute.fset))


    return cast(Type[Aggregate], aggregate_cls)


class event:
    def __init__(self, arg: Union[FunctionType, str]):
        self.is_property_setter = False
        self.propery_attribute_name = None
        assert isinstance(arg, (FunctionType, str))
        if isinstance(arg, FunctionType):
            self.original_method = arg
            name = arg.__name__
            self.event_cls_name = "".join([s.capitalize() for s in name.split("_")])
        elif isinstance(arg, str):
            self.event_cls_name = arg
            self.original_method = None

    def __call__(self, *args, **kwargs):
        if self.original_method is None:
            assert len(kwargs) == 0
            assert len(args) == 1
            assert isinstance(args[0], (FunctionType, property))
            self.original_method = args[0]
            return self
        elif len(args) == 2 and len(kwargs) == 0 and isinstance(args[0], Aggregate):
            # Property assignment?
            assert self.is_property_setter
            kwargs = {self.propery_attribute_name: args[1]}
            bound = bound_event(self, args[0])
            bound.trigger(**kwargs)
        else:
            assert self.event_cls_name is not None
            assert self.original_method is not None
            self.original_method(*args, **kwargs)


class bound_event:
    def __init__(self, event: event, aggregate: Aggregate):
        self.event = event
        self.aggregate = aggregate

    def trigger(self, **kwargs):
        event_cls = getattr(self.aggregate, self.event.event_cls_name)
        self.aggregate._trigger_event(event_cls, **kwargs)

    def __call__(self, *args, **kwargs):
        self.trigger(**kwargs)
