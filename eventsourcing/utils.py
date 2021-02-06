import importlib
from types import ModuleType
from typing import Any, Dict


def get_topic(cls: type) -> str:
    """
    Returns a string that locates the given class.
    """
    return f"{cls.__module__}:{cls.__qualname__}"


def resolve_topic(topic: str) -> Any:
    """
    Returns a class located by the given string.
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


try:
    from functools import singledispatchmethod
except ImportError:  # pragma: no cover
    from functools import singledispatch, update_wrapper

    def singledispatchmethod(func):  # type: ignore
        dispatcher = singledispatch(func)

        def wrapper(*args, **kwargs):  # type: ignore
            return dispatcher.dispatch(args[1].__class__)(*args, **kwargs)

        wrapper.register = dispatcher.register
        update_wrapper(wrapper, func)
        return wrapper
