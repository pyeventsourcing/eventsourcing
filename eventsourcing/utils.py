import importlib
from types import ModuleType
from typing import Any, Dict


def get_topic(cls: type) -> str:
    """
    Returns a string that locates the given class.
    """
    topic = f"{cls.__module__}:{cls.__qualname__}"
    _objs_cache[topic] = cls
    return topic


# Todo: Implement substitutions, so classes can be moved to another module.
def resolve_topic(topic: str) -> Any:
    """
    Returns an object located by the given string.
    """
    try:
        obj = _objs_cache[topic]
    except KeyError:
        module_name, _, class_name = topic.partition(":")
        module = get_module(module_name)
        obj = resolve_attr(module, class_name)
        _objs_cache[topic] = obj
    return obj


_objs_cache: Dict[str, Any] = {}


def get_module(module_name: str) -> ModuleType:
    try:
        module = _modules_cache[module_name]
    except KeyError:
        module = importlib.import_module(module_name)
        _modules_cache[module_name] = module
    return module


_modules_cache: Dict[str, Any] = {}


def resolve_attr(obj: Any, path: str) -> Any:
    if not path:
        return obj
    else:
        head, _, tail = path.partition(".")
        obj = getattr(obj, head)
        return resolve_attr(obj, tail)
