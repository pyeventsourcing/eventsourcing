from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator, Mapping
from functools import wraps
from inspect import isfunction
from random import random
from threading import Lock
from time import sleep
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    NewType,
    get_args,
    get_origin,
    no_type_check,
    overload,
)

from typing_extensions import TypeVar, get_original_bases

if TYPE_CHECKING:
    from types import FunctionType, WrapperDescriptorType


class TopicError(Exception):
    """Raised when topic doesn't resolve."""


SupportsTopic = type | Callable[..., Any] | ModuleType

_type_cache: dict[SupportsTopic, str] = {}
_topic_cache: dict[str, SupportsTopic] = {}
_topic_cache_lock = Lock()


def get_topic(obj: SupportsTopic, /) -> str:
    """Returns a "topic string" that locates the given class
    in its module. The string is formed by joining the
    module name and the class qualname separated by the
    colon character.
    """
    try:
        return _type_cache[obj]
    except KeyError:
        topic = construct_topic(obj)
        register_topic(topic, obj)
        _type_cache[obj] = topic
        return topic


def construct_topic(obj: SupportsTopic, /) -> str:
    return getattr(obj, "TOPIC", f"{obj.__module__}:{obj.__qualname__}")


def resolve_topic(topic: str) -> Any:
    """Returns an object located by the given topic.

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
                        module_name = ".".join([obj.__name__, *module_name_parts[i:]])
                        break
                try:
                    obj = importlib.import_module(module_name)
                except ImportError as e:
                    msg = f"Failed to resolve topic '{topic}': {e}"
                    raise TopicError(msg) from e
        if attr_name:
            try:
                for attr_name_part in attr_name.split("."):
                    obj = getattr(obj, attr_name_part)
            except AttributeError as e:
                msg = f"Failed to resolve topic '{topic}': {e}"
                raise TopicError(msg) from e
        register_topic(topic, obj)
    return obj


def register_topic(topic: str, obj: SupportsTopic) -> None:
    """Registers a topic with an object, so the object will be
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
                msg = (
                    f"Refusing to cache {obj} (oid {id(obj)}): {cached_obj} (oid "
                    f"{id(cached_obj)}) is already registered for topic '{topic}'"
                )
                raise TopicError(msg)


def clear_topic_cache() -> None:
    _topic_cache.clear()


def retry(
    exc: type[Exception] | tuple[type[Exception], ...] = Exception,
    max_attempts: int = 1,
    wait: float = 0,
    stall: float = 0,
) -> Callable[[Any], Any]:
    """Retry decorator.

    :param exc: List of exceptions that will cause the call to be retried if raised.
    :param max_attempts: Maximum number of attempts to try.
    :param wait: Amount of time to wait before retrying after an exception.
    :param stall: Amount of time to wait before the first attempt.
    :return: Returns the value returned by decorated function.
    """

    @no_type_check
    def _retry(func: Callable) -> Callable:
        @wraps(func)
        def retry_decorator(*args: Any, **kwargs: Any) -> Any:
            if stall:
                sleep(stall)
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exc:
                    attempts += 1
                    if max_attempts is None or attempts < max_attempts:
                        sleep(wait * (1 + 0.1 * (random() - 0.5)))  # noqa: S311
                    else:
                        # Max retries exceeded.
                        raise

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
    # Check decorator args, and return _retry,
    # to be called with the decorated function.
    if isinstance(exc, (list, tuple)):
        for _exc in exc:
            if not (isinstance(_exc, type) and issubclass(_exc, Exception)):
                msg = f"not an exception class: {_exc}"
                raise TypeError(msg)
    elif not (isinstance(exc, type) and issubclass(exc, Exception)):
        msg = f"not an exception class: {exc}"
        raise TypeError(msg)
    if not isinstance(max_attempts, int):
        msg = f"'max_attempts' must be an int: {max_attempts}"
        raise TypeError(msg)
    if not isinstance(wait, (float, int)):
        msg = f"'wait' must be a float: {max_attempts}"
        raise TypeError(msg)
    if not isinstance(stall, (float, int)):
        msg = f"'stall' must be a float: {max_attempts}"
        raise TypeError(msg)
    return _retry


def strtobool(val: str) -> bool:
    """Convert a string representation of truth to True or False.

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    if not isinstance(val, str):
        msg = f"{val} is not a str"
        raise TypeError(msg)
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    if val in ("n", "no", "f", "false", "off", "0"):
        return False
    msg = f"invalid truth value {val!r}"
    raise ValueError(msg)


def reversed_keys(d: dict[Any, Any]) -> Iterator[Any]:
    return reversed(d.keys())


# TODO: Inline this now.
def get_method_name(
    method: Callable[..., Any] | FunctionType | WrapperDescriptorType,
) -> str:
    return method.__qualname__


EnvType = Mapping[str, str]
T = TypeVar("T")


class Environment(dict[str, str]):
    def __init__(self, name: str = "", env: EnvType | None = None):
        super().__init__(env or {})
        self.name = name

    @overload  # type: ignore[override]
    def get(self, __key: str, /) -> str | None: ...  # pragma: no cover

    @overload
    def get(self, __key: str, /, __default: str) -> str: ...  # pragma: no cover

    @overload
    def get(self, __key: str, /, __default: T) -> str | T: ...  # pragma: no cover

    def get(  # pyright: ignore [reportIncompatibleMethodOverride]
        self, __key: str, /, __default: str | T | None = None
    ) -> str | T | None:
        for _key in self.create_keys(__key):
            value = super().get(_key, None)
            if value is not None:
                return value
        return __default

    def create_keys(self, key: str) -> list[str]:
        keys = []
        if self.name:
            keys.append(self.name.upper() + "_" + key)
        keys.append(key)
        return keys


def resolve_multi_generic_target(
    cls: type, target_base: type, *, _verbose: bool = False
) -> tuple[Any, ...]:
    """
    Finds type arguments for `target_base` of given `cls`.
    """
    # if verbose:
    #     print(f"Resolving multi generic target {cls}...")

    target_params = safe_get_params(target_base)
    if not target_params:
        # if verbose:
        #     print(f"Resolved {()} for {cls}")
        return ()

    # Map each class in the MRO to a dictionary of its own resolved type parameters
    # eg. {IntermediateApp: {~T: <class 'str'>}, Application: {~TAggID: <class 'str'>}}
    resolved_params: dict[type, dict[Any, Any]] = {cls: {}}

    for ancestor in cls.__mro__:
        if ancestor not in resolved_params:
            # Only get here with a "sneaky" mro.
            resolved_params[ancestor] = {}

        # The context dictionary of the current class we are looking at
        current_context = resolved_params[ancestor]

        orig_bases = safe_get_original_bases(ancestor)

        for base in orig_bases:
            origin = safe_get_origin(base)
            if origin is None:
                # Unparameterized inheritance (e.g., class Child(Parent): ...)
                origin = base
                args = ()
            else:
                args = safe_get_args(base)
            # if verbose:
            #     print(f" - Args {args} for base {base}")

            ancestor_params = safe_get_params(origin)

            if origin not in resolved_params:
                resolved_params[origin] = {}

            # Evaluate what the child is passing to the parent
            # Note: zip with `strict=True` raises when base is typing.Generic.
            arg: Any
            for param, arg in zip(ancestor_params, args, strict=False):
                # If the argument is a TypeVar, resolve it using the child's context
                if isinstance(arg, TypeVar) and arg in current_context:
                    resolved_arg = current_context[arg]
                else:
                    resolved_arg = arg

                # Store exactly what this specific parent class received
                resolved_params[origin][param] = resolved_arg

    final_output = []

    # Look specifically at what was passed into the target_base
    target_context = resolved_params.get(target_base, {})

    for param in target_params:
        # Get the resolved value if it exists, otherwise fall back to the param itself
        resolved_val = target_context.get(param, param)

        if isinstance(resolved_val, TypeVar):
            # Only evaluate the default of the CURRENTLY bound TypeVar
            if hasattr(resolved_val, "has_default") and resolved_val.has_default():
                final_output.append(resolved_val.__default__)
            else:
                final_output.append(None)  # It's an unresolved TypeVar with no default
        else:
            final_output.append(resolved_val)

    # if verbose:
    #     print(f"Resolved {final_output} for {cls}")
    return tuple(final_output)


def safe_get_origin(tp: Any) -> Any:
    """Pydantic-aware version of typing.get_origin."""
    # Check if it's a parameterized Pydantic model class
    metadata = getattr(tp, "__pydantic_generic_metadata__", None)
    if metadata and isinstance(metadata, dict):
        return metadata.get("origin")
    return get_origin(tp)


def safe_get_args(tp: Any) -> tuple[Any, ...]:
    """Pydantic-aware version of typing.get_args."""
    metadata = getattr(tp, "__pydantic_generic_metadata__", None)
    if metadata and isinstance(metadata, dict):
        return metadata.get("args", ())
    return get_args(tp)


def safe_get_params(tp: Any) -> tuple[Any, ...]:
    """Pydantic-aware version of fetching __parameters__."""
    metadata = getattr(tp, "__pydantic_generic_metadata__", None)
    if metadata and isinstance(metadata, dict):
        return metadata.get("parameters", ())

    # Fallback to standard Python generic parameters
    return getattr(tp, "__parameters__", ())


def safe_get_original_bases(cls: type) -> tuple[Any, ...]:
    """
    Pydantic-aware version of get_original_bases.
    Repairs mangled __orig_bases__ by pulling concrete Pydantic generic
    models back out of the standard __bases__ tuple.
    """
    # 1. Start with Python's standard resolution
    orig_bases = get_original_bases(cls)

    # 2. If the lengths differ, complex __mro_entries__ unpacking occurred
    # (e.g. TypedDict or NamedTuple). It is safer to return as-is.
    if len(orig_bases) != len(cls.__bases__):
        return orig_bases

    repaired_bases = []

    # 3. Zip them together. Their relative order is identical.
    for orig_b, real_b in zip(orig_bases, cls.__bases__, strict=False):
        # If the actual base is a parameterized Pydantic model, it holds the truth.
        # It carries __pydantic_generic_metadata__ which our safe_get_args needs.
        if hasattr(real_b, "__pydantic_generic_metadata__"):
            repaired_bases.append(real_b)

        # Otherwise, it's a standard Python generic alias (like Generic[T]),
        # so we must use the orig_b to preserve the type arguments.
        else:
            repaired_bases.append(orig_b)

    return tuple(repaired_bases)


_T = TypeVar("_T")


def unwrap_new_type(id_type: type[_T]) -> type[_T]:
    while True:
        if isinstance(id_type, type):
            return id_type
        assert isinstance(id_type, NewType), id_type
        id_type = id_type.__supertype__
