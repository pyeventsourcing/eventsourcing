import importlib
from dataclasses import dataclass


def get_topic(cls: type) -> str:
    """
    Returns a string that locates the given class.
    """
    return f"{cls.__module__}:{cls.__qualname__}"


def resolve_topic(topic: str) -> type:
    """
    Returns a class located by the given string.
    """
    module_name, _, class_name = topic.partition(":")
    module = importlib.import_module(module_name)
    return resolve_attr(module, class_name)


def resolve_attr(obj, path: str) -> type:
    if not path:
        return obj
    else:
        head, _, tail = path.partition(".")
        obj = getattr(obj, head)
        return resolve_attr(obj, tail)


class FrozenDataClass(type):
    def __new__(cls, *args):
        new_cls = super().__new__(cls, *args)
        return dataclass(frozen=True)(new_cls)


class ImmutableObject(metaclass=FrozenDataClass):
    pass
