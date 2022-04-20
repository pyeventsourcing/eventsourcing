import importlib
import sys
from functools import wraps
from inspect import isfunction
from random import random
from threading import Lock
from time import sleep
from types import FunctionType, WrapperDescriptorType
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    no_type_check,
    overload,
)


class TopicError(Exception):
    """
    Raised when topic doesn't resolve.
    """


_type_cache: Dict[type, str] = {}
_topic_cache: Dict[str, Any] = {}
_topic_cache_lock = Lock()


def get_topic(cls: type) -> str:
    """
    Returns a "topic string" that locates the given class
    in its module. The string is formed by joining the
    module name and the class qualname separated by the
    colon character.
    """
    try:
        return _type_cache[cls]
    except KeyError:
        topic = f"{cls.__module__}:{cls.__qualname__}"
        register_topic(topic, cls)
        _type_cache[cls] = topic
        return topic


def resolve_topic(topic: str) -> Any:
    """
    Returns an object located by the given topic.

    This function can be (is) used to locate domain
    event classes and aggregate classes from the
    topics in stored events and snapshots. It can
    also be used to locate compression modules,
    timezone objects, etc.
    """
    try:
        obj = _topic_cache[topic]
    except KeyError:
        module_name, _, attr_name = topic.partition(":")

        attr_name_parts = attr_name.split(".")
        for i in range(len(attr_name_parts) - 1, 0, -1):
            part_name = ".".join(attr_name_parts[:i])
            try:
                obj = _topic_cache[f"{module_name}:{part_name}"]
            except KeyError:
                continue
            else:
                attr_name = ".".join(attr_name_parts[i:])
                break

        else:
            try:
                obj = _topic_cache[module_name]
            except KeyError:
                module_name_parts = module_name.split(".")
                for i in range(len(module_name_parts) - 1, 0, -1):
                    part_name = ".".join(module_name_parts[:i])
                    try:
                        obj = _topic_cache[f"{part_name}"]
                    except KeyError:
                        continue
                    else:
                        module_name = ".".join([obj.__name__] + module_name_parts[i:])
                        break
                try:
                    obj = importlib.import_module(module_name)
                except ImportError as e:
                    msg = f"Failed to resolve topic '{topic}': {e}"
                    raise TopicError(msg) from e
        if attr_name:
            for attr_name_part in attr_name.split("."):
                try:
                    obj = getattr(obj, attr_name_part)
                except AttributeError as e:
                    msg = f"Failed to resolve topic '{topic}': {e}"
                    raise TopicError(msg) from e
        register_topic(topic, obj)
    return obj


def register_topic(topic: str, obj: Any) -> None:
    """
    Registers a topic with an object, so the object will be
    returned whenever the topic is resolved.

    This function can be used to cache the topic of a class, so
    that the topic can be resolved faster. It can also be used to
    register old topics for objects that have been renamed or moved,
    so that old topics will resolve to the renamed or moved object.
    """
    with _topic_cache_lock:
        try:
            cached_obj = _topic_cache[topic]
        except KeyError:
            _topic_cache[topic] = obj
        else:
            if cached_obj != obj:
                raise TopicError(
                    f"Object {cached_obj} is already registered "
                    f"for topic '{topic}', so refusing to cache obj {obj}"
                )


def clear_topic_cache() -> None:
    _topic_cache.clear()


def retry(
    exc: Union[Type[Exception], Sequence[Type[Exception]]] = Exception,
    max_attempts: int = 1,
    wait: float = 0,
    stall: float = 0,
) -> Callable[[Any], Any]:
    """
    Retry decorator.

    :param exc: List of exceptions that will cause the call to be retried if raised.
    :param max_attempts: Maximum number of attempts to try.
    :param wait: Amount of time to wait before retrying after an exception.
    :param stall: Amount of time to wait before the first attempt.
    :param verbose: If True, prints a message to STDOUT when retries occur.
    :return: Returns the value returned by decorated function.
    """

    @no_type_check
    def _retry(func):
        @wraps(func)
        def retry_decorator(*args, **kwargs):
            if stall:
                sleep(stall)
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exc as e:
                    attempts += 1
                    if max_attempts is None or attempts < max_attempts:
                        sleep(wait * (1 + 0.1 * (random() - 0.5)))
                    else:
                        # Max retries exceeded.
                        raise e

        return retry_decorator

    # If using decorator in bare form, the decorated
    # function is the first arg, so check 'exc'.
    if isfunction(exc):
        # Remember the given function.
        _func = exc
        # Set 'exc' to a sensible exception class for _retry().
        exc = Exception
        # Wrap and return.
        return _retry(func=_func)
    else:
        # Check decorator args, and return _retry,
        # to be called with the decorated function.
        if isinstance(exc, (list, tuple)):
            for _exc in exc:
                if not (isinstance(_exc, type) and issubclass(_exc, Exception)):
                    raise TypeError("not an exception class: {}".format(_exc))
        else:
            if not (isinstance(exc, type) and issubclass(exc, Exception)):
                raise TypeError("not an exception class: {}".format(exc))
        if not isinstance(max_attempts, int):
            raise TypeError("'max_attempts' must be an int: {}".format(max_attempts))
        if not isinstance(wait, (float, int)):
            raise TypeError("'wait' must be a float: {}".format(max_attempts))
        if not isinstance(stall, (float, int)):
            raise TypeError("'stall' must be a float: {}".format(max_attempts))
        return _retry


def strtobool(val: str) -> bool:
    """Convert a string representation of truth to True or False.

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    if not isinstance(val, str):
        raise TypeError(f"{val} is not a str")
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError("invalid truth value %r" % (val,))


def reversed_keys(d: Dict[Any, Any]) -> Iterator[Any]:
    if sys.version_info >= (3, 8):  # pragma: no cover
        return reversed(d.keys())
    else:  # pragma: no cover
        return reversed(list(d.keys()))


def get_method_name(method: Union[FunctionType, WrapperDescriptorType]) -> str:
    if sys.version_info >= (3, 10):  # pragma: no cover
        return method.__qualname__
    else:  # pragma: no cover
        return method.__name__


EnvType = Mapping[str, str]
T = TypeVar("T")


class Environment(Dict[str, str]):
    def __init__(self, name: str = "", env: Optional[EnvType] = None):
        super().__init__(env or {})
        self.name = name

    @overload
    def get(self, key: str) -> Optional[str]:
        ...  # pragma: no cover

    @overload
    def get(self, key: str, default: Union[str, T]) -> Union[str, T]:
        ...  # pragma: no cover

    def get(
        self, key: str, default: Optional[Union[str, T]] = None
    ) -> Optional[Union[str, T]]:
        for _key in self.create_keys(key):
            value = super().get(_key, None)
            if value is not None:
                return value
        return default

    def create_keys(self, key: str) -> List[str]:
        keys = []
        if self.name:
            keys.append(self.name.upper() + "_" + key)
        keys.append(key)
        return keys
