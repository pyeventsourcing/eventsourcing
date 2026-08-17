from __future__ import annotations

import dataclasses
import inspect
import typing
from abc import ABCMeta
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any, dataclass_transform, override
from uuid import UUID

import eventsourcing.domain


@dataclass_transform(frozen_default=True, kw_only_default=True)
class MetaImmutable(ABCMeta):
    def __call__(cls, **kwargs: Any) -> Any:
        validated_kwargs: dict[str, Any] = {}
        init_types = get_init_types(cls)

        for key, value in kwargs.items():
            if key in init_types:
                validated_kwargs[key] = coerce_value(init_types[key], value)
            else:
                validated_kwargs[key] = value

        return super().__call__(**validated_kwargs)

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        cls_dict: dict[str, Any],
    ) -> Any:
        event_cls = typing.cast(type[Any], super().__new__(mcs, name, bases, cls_dict))
        event_cls = dataclasses.dataclass(frozen=True, kw_only=True)(event_cls)

        typing.cast(Any, event_cls).__signature__ = inspect.signature(
            event_cls.__init__
        )
        return event_cls


@lru_cache
def get_init_types(cls: type[Any]) -> dict[str, Any]:
    # 1. Resolve all type hints for the class safely
    resolved_hints = typing.get_type_hints(cls)

    # 2. Filter down to only fields included in __init__
    return {
        field.name: resolved_hints[field.name]
        for field in dataclasses.fields(cls)
        if field.init
    }


class Immutable(metaclass=MetaImmutable):
    pass


class Decision(Immutable, eventsourcing.domain.Decision):
    @override
    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class TaggedEvent(eventsourcing.domain.AggregateEvent[Decision]):
    pass


class AggregateEvent(eventsourcing.domain.AggregateEvent[Decision]):
    pass


class ImmutableAggregate(Immutable):
    id: str
    version: int


class ImmutableAggregateSnapshot(Decision):
    state: dict[str, Any]

    @classmethod
    def take(cls, aggregate: ImmutableAggregate) -> AggregateEvent:
        decision = cls(
            state=aggregate.__dict__.copy(),
        )
        return AggregateEvent(
            decision=decision,
            originator_id=aggregate.id,
            originator_version=aggregate.version,
        )


def coerce_value(expected_type: type[Any], value: Any) -> Any:  # noqa: PLR0911
    """Recursively coerces primitive/JSON types into their expected Python types."""
    # 1. Handle None values safely
    if value is None:
        return None

    origin = typing.get_origin(expected_type) or expected_type

    # 2. Normalize bare `typing` aliases to built-ins
    if origin is getattr(typing, "Tuple", None):
        origin = tuple
    if origin is getattr(typing, "List", None):
        origin = list
    if origin is getattr(typing, "Dict", None):
        origin = dict
    if origin is getattr(typing, "Set", None):
        origin = set
    if origin is getattr(typing, "FrozenSet", None):
        origin = frozenset

    args = typing.get_args(expected_type)

    # 3. Handle Optional/Union types (e.g., int | None)
    if origin is typing.Union or getattr(origin, "__name__", "") == "UnionType":
        for arg_type in args:
            if arg_type is type(None):
                continue
            try:
                return coerce_value(arg_type, value)
            except (ValueError, TypeError):
                continue
        return value

    # 4. Handle Collections (Lists, Sets, Tuples, Dicts)
    if origin in (list, set, frozenset):
        if not args:
            return origin(value)
        item_type = args[0]
        return origin(coerce_value(item_type, item) for item in value)

    if origin is tuple:
        if not args:
            return tuple(value)
        # Variable-length tuple: tuple[T, ...]
        if len(args) == 2 and args[1] is Ellipsis:
            item_type = args[0]
            return tuple(coerce_value(item_type, item) for item in value)
        # Fixed-length tuple: tuple[T1, T2]
        return tuple(
            coerce_value(arg_type, item)
            for arg_type, item in zip(args, value, strict=False)
        )

    if origin is dict:
        if not args:
            return dict(value)
        key_type, val_type = args
        return {
            coerce_value(key_type, k): coerce_value(val_type, v)
            for k, v in value.items()
        }

    # 5. If it already matches the exact type, return as-is
    try:
        if isinstance(value, expected_type):
            return value
    except TypeError:
        # Catch errors if expected_type is an unhandled
        # subscripted generic (e.g., Sequence[int])
        pass

    # 6. Handle built-in types that require specific string parsing
    if expected_type is UUID:
        return UUID(value)
    if expected_type is datetime:
        return datetime.fromisoformat(value)
    if expected_type is date:
        return date.fromisoformat(value)
    if expected_type is Decimal:
        return Decimal(str(value))

    # 7. Handle nested standard dataclasses recursively
    if dataclasses.is_dataclass(expected_type) and isinstance(value, dict):
        init_types = get_init_types(expected_type)
        coerced_kwargs = {}
        for k, v in value.items():
            if k in init_types:
                coerced_kwargs[k] = coerce_value(init_types[k], v)
            else:
                coerced_kwargs[k] = v
        return expected_type(**coerced_kwargs)

    # 8. Fallback for custom objects or primitives
    if isinstance(value, dict):
        return expected_type(**value)

    try:
        return expected_type(value)  # pyright: ignore [reportCallIssue]
    except Exception:
        return value
