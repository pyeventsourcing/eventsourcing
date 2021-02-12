import inspect
from copy import copy
from dataclasses import dataclass
from typing import Type, cast
from uuid import uuid4

from eventsourcing.domain import Aggregate


def aggregate(cls) -> Type[Aggregate]:
    new_cls = type(cls.__name__, (cls, Aggregate), {})
    new_cls.__qualname__ = cls.__qualname__
    new_cls.__module__ = cls.__module__
    new_cls.__doc__ = cls.__doc__

    created_cls = Aggregate.Created

    def apply(self, aggregate):
        event_obj_dict = copy(self.__dict__)
        event_obj_dict.pop("originator_id")
        event_obj_dict.pop("originator_version")
        event_obj_dict.pop("timestamp")
        self.original_method(aggregate, **event_obj_dict)

    for name in dir(cls):
        attribute = getattr(cls, name)
        if isinstance(attribute, event):
            # Prepare the subsequent aggregate events.
            original_method = attribute.original_method
            event_cls_name = "".join([s.capitalize() for s in name.split("_")])

            event_cls_qualname = ".".join([cls.__qualname__, event_cls_name])

            method_signature = inspect.signature(original_method)
            annotations = {}
            for param_name in method_signature.parameters:
                if param_name == "self":
                    continue
                annotations[param_name] = "typing.Any"

            event_cls_dict = {"__annotations__": annotations}

            event_cls = type(event_cls_name, (Aggregate.Event,), event_cls_dict)

            event_cls = dataclass(event_cls, frozen=True)
            event_cls.__qualname__ = event_cls_qualname
            event_cls.__module__ = cls.__module__

            event_cls.apply = apply
            event_cls.original_method = staticmethod(original_method)
            setattr(new_cls, event_cls_name, event_cls)
        elif name == "__init__":
            # Prepare the "created" event.
            method_signature = inspect.signature(attribute)
            annotations = {}
            for param_name in method_signature.parameters:
                if param_name == "self":
                    continue
                annotations[param_name] = "typing.Any"

            event_cls_dict = {"__annotations__": annotations}

            created_cls = type("Created", (Aggregate.Created,), event_cls_dict)
            created_cls.__qualname__ = ".".join([cls.__qualname__, "Created"])
            created_cls.__module__ = cls.__module__

            new_cls.Created = created_cls

            created_cls = dataclass(created_cls, frozen=True)

    original_init = new_cls.__init__

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            return  # Python calls me again...
        base_kwargs = {}
        base_kwargs["id"] = kwargs.pop("id")
        base_kwargs["version"] = kwargs.pop("version")
        base_kwargs["timestamp"] = kwargs.pop("timestamp")
        Aggregate.__init__(self, **base_kwargs)
        original_init(self, **kwargs)

    cls.__init__ = __init__

    def __new__(cls, **kwargs):
        return cls._create(event_class=created_cls, id=uuid4(), **kwargs)

    new_cls.__new__ = __new__

    return cast(Type[Aggregate], new_cls)


class event:
    def __init__(self, original_method):
        self.original_method = original_method
