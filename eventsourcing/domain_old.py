# from __future__ import annotations
#
# import contextlib
# import dataclasses
# import importlib
# import inspect
# import os
# import types
# import typing
# from abc import ABCMeta
# from collections import defaultdict
# from collections.abc import Callable, Iterable
# from dataclasses import dataclass, field
# from datetime import datetime
# from types import FunctionType, GenericAlias
# from typing import (
#     TYPE_CHECKING,
#     Any,
#     ClassVar,
#     Generic,
#     Protocol,
#     cast,
#     overload,
#     runtime_checkable,
# )
# from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5
# from warnings import warn
#
# from typing_extensions import TypeVar
#
# # from eventsourcing.domain_new import NIL_UUID, datetime_now_with_tzinfo, \
# #     AbstractDecision, get_metadata_from_context, EventSourcingError, ProgrammingError, \
# #     filter_kwargs_for_method_params, CallableType, TDecoratableType, \
# #     CommandMethodDecorator, decorated_func_callers, \
# #     _raise_type_error_if_func_has_variable_params, _coerce_args_to_kwargs
# from eventsourcing.utils import (
#     TopicError,
#     get_topic,
#     register_topic,
#     resolve_multi_generic_target,
#     resolve_topic,
#     safe_get_args,
#     safe_get_origin,
#     safe_get_original_bases,
#     safe_get_params,
#     unwrap_new_type,
# )
#
# if TYPE_CHECKING:
#     from collections.abc import Sequence
#     from typing import Self
#
# """
# A Python :py:obj:`tzinfo` object that defaults to UTC (:py:obj:`timezone.utc`). Used
# as the timezone argument in :func:`~eventsourcing.domain.datetime_now_with_tzinfo`.
#
# Set environment variable ``TZINFO_TOPIC`` to the topic of a different :py:obj:`tzinfo`
# object so that all your domain model event timestamps are located in that timezone
# (not recommended). It is generally recommended to locate all timestamps in the UTC
# domain and convert to local timezones when presenting values in user interfaces.
# """
#
# """
# Offical Nil UUID ID sentinel, used to detect and fill missing IDs in legacy databases.
# """
#
# """
# Offical Nil str ID sentinel, used to detect and fill missing IDs in legacy databases.
# """
#
# LEGACY_NAMESPACE = uuid5(NAMESPACE_DNS, "eventsourcing.python.library")
#
#
# def event_id_from_originator_id_and_version(
#     originator_id: UUID | str,
#     originator_version: int,
# ) -> UUID:
#     """
#     Generates a deterministic event ID from originator ID and version.
#     """
#     fallback_str = f"{originator_id}:{originator_version}"
#     return uuid5(LEGACY_NAMESPACE, fallback_str)
#
#
# class EventsourcingType(type):
#     """Base type for event sourcing domain model types (aggregates and events)."""
#
#
# _T = TypeVar("_T")
#
#
# def patch_dataclasses_process_class() -> None:
#     dataclasses_module = importlib.import_module("dataclasses")
#     original_process_class_func = dataclasses_module.__dict__["_process_class"]
#
#     def _patched_dataclasses_process_class(
#         cls: type[_T], *args: Any, **kwargs: Any
#     ) -> type[_T]:
#         # Avoid processing aggregate and event dataclasses twice,
#         # because doing so screws up non-init and default fields.
#         if (
#             cls
#             and isinstance(cls, EventsourcingType)
#             and "__dataclass_fields__" in cls.__dict__
#         ):
#             return cls
#         return original_process_class_func(cls, *args, **kwargs)
#
#     dataclasses_module.__dict__["_process_class"] = _patched_dataclasses_process_class
#
#
# patch_dataclasses_process_class()
#
#
# TAggregateID = TypeVar("TAggregateID", bound=UUID | str, default=UUID)
# TAggregateID_co = TypeVar(
#     "TAggregateID_co", bound=UUID | str, covariant=True, default=UUID
# )
#
#
# @runtime_checkable
# class DomainEventProtocol(Protocol[TAggregateID_co]):
#     """Protocol for domain event objects.
#
#     A protocol is defined to allow the event sourcing mechanisms
#     to work with different kinds of domain event classes. Whilst
#     the library by default uses frozen dataclasses to implement
#     its domain event classes, it is also possible to use other
#     kinds of domain event classes, such as Pydantic classes.
#     """
#
#     def __init__(self, *args: Any, **kwargs: Any) -> None:
#         pass  # pragma: no cover
#
#     @property
#     def originator_id(self) -> TAggregateID_co:
#         """UUID identifying an aggregate to which the event belongs."""
#         raise NotImplementedError  # pragma: no cover
#
#     @property
#     def originator_version(self) -> int:
#         """Integer identifying the version of the aggregate when the event occurred."""
#         raise NotImplementedError  # pragma: no cover
#
#     @property
#     def metadata(self) -> dict[str, str]:
#         """Event metadata."""
#         raise NotImplementedError  # pragma: no cover
#
#     @property
#     def event_id(self) -> UUID:
#         """Event identifier."""
#         raise NotImplementedError  # pragma: no cover
#
#
# TDomainEvent = TypeVar("TDomainEvent", bound=DomainEventProtocol[Any])
# SDomainEvent = TypeVar("SDomainEvent", bound=DomainEventProtocol[Any])
#
#
# class MutableAggregateProtocol(Protocol[TAggregateID_co]):
#     """Protocol for mutable aggregate objects.
#
#     A protocol is defined to allow the event sourcing mechanisms
#     to work with different kinds of aggregate classes. Whilst
#     the library by default recommends using mutable classes to
#     implement aggregate classes, it is also possible to implement
#     immutable aggregate classes, and this is supported by this library.
#     """
#
#     @property
#     def id(self) -> TAggregateID_co:
#         """Mutable aggregates have a read-only ID that is a UUID."""
#         raise NotImplementedError  # pragma: no cover
#
#     @property
#     def version(self) -> int:
#         """Mutable aggregates have a read-write version that is an int."""
#         raise NotImplementedError  # pragma: no cover
#
#     @version.setter
#     def version(self, value: int) -> None:
#         """Mutable aggregates have a read-write version that is an int."""
#         raise NotImplementedError  # pragma: no cover
#
#
# class ImmutableAggregateProtocol(Protocol[TAggregateID_co]):
#     """Protocol for immutable aggregate objects.
#
#     A protocol is defined to allow the event sourcing mechanisms
#     to work with different kinds of aggregate classes. Whilst
#     the library by default recommends using mutable classes to
#     implement aggregate classes, it is also possible to implement
#     immutable aggregate classes, and this is supported by this library.
#     """
#
#     @property
#     def id(self) -> TAggregateID_co:
#         """Immutable aggregates have a read-only ID that is a UUID."""
#         raise NotImplementedError  # pragma: no cover
#
#     @property
#     def version(self) -> int:
#         """Immutable aggregates have a read-only version that is an int."""
#         raise NotImplementedError  # pragma: no cover
#
#
# MutableOrImmutableAggregate = (
#     ImmutableAggregateProtocol[TAggregateID] | MutableAggregateProtocol[TAggregateID]
# )
# """Type alias defining a union of mutable and immutable aggregate protocols."""
#
#
# TMutableAggregate = TypeVar("TMutableAggregate", bound=MutableAggregateProtocol[Any])
# """Type variable bound by the mutable aggregate protocols."""
#
#
# TMutableOrImmutableAggregate = TypeVar(
#     "TMutableOrImmutableAggregate", bound=MutableOrImmutableAggregate[Any]
# )
# """Type variable bound by the union of mutable and immutable aggregate protocols."""
#
#
#
#
#
#
#
#
# def create_utc_datetime_now() -> datetime:
#     """Deprected in favour of :func:`~eventsourcing.domain.datetime_now_with_tzinfo`."""
#     msg = (
#         "'create_utc_datetime_now()' is deprecated, "
#         "use 'datetime_now_with_tzinfo()' instead"
#     )
#     warn(msg, DeprecationWarning, stacklevel=2)
#     return datetime_now_with_tzinfo()
#
#
# def _is_sub_hasoriginatoridversion(obj: Any) -> bool:
#     return isinstance(obj, type) and issubclass(obj, HasOriginatorIDVersion)
#
#
# def _is_sub_cansnapshotaggregate(obj: Any) -> bool:
#     return isinstance(obj, type) and issubclass(obj, CanSnapshotAggregate)
#
#
# def _is_sub_canmutateaggregate(obj: Any) -> bool:
#     return isinstance(obj, type) and issubclass(obj, CanMutateAggregate)
#
#
# def _is_sub_caninitaggregate(obj: Any) -> bool:
#     return isinstance(obj, type) and issubclass(obj, CanInitAggregate)
#
#
# def _get_originator_type_id(
#     cls: type[HasOriginatorIDVersion[Any] | BaseAggregate[Any]] | GenericAlias,
# ) -> type[UUID | str] | None:
#     # TODO: Replace this with custom generic alias that does this work.
#     origin = safe_get_origin(cls)
#     args = safe_get_args(cls)
#
#     target_param_idx = None
#     origin_params = safe_get_params(origin) if origin else ()
#     for idx, param in enumerate(origin_params):
#         if idx < len(args) and param == TAggregateID:
#             target_param_idx = idx
#             break
#
#     if target_param_idx is not None:
#         return args[target_param_idx]
#     return cls.originator_id_type
#
#
# TAggregate = TypeVar("TAggregate", bound="BaseAggregate[Any]")
#
#
# class HasOriginatorIDVersion(AbstractDecision, Generic[TAggregateID]):
#     """Declares ``originator_id`` and ``originator_version`` attributes."""
#
#     originator_id: TAggregateID
#     """UUID identifying an aggregate to which the event belongs."""
#     originator_version: int
#     """Integer identifying the version of the aggregate when the event occurred."""
#
#     originator_id_type: ClassVar[type[UUID | str]] = UUID
#
#     def __init_subclass__(cls, **kwargs: Any) -> None:
#         super().__init_subclass__(**kwargs)
#
#         # Look at the immediate bases of the new class being created
#         orig_bases = safe_get_original_bases(cls)
#
#         # 1. ORIGINATOR ID CONSISTENCY CHECK
#         collected_id_types: set[Any] = set()
#
#         for base in orig_bases:
#             if _is_sub_hasoriginatoridversion(safe_get_origin(base) or base):
#                 id_type = _get_originator_type_id(base)
#
#                 # Only collect concrete types (e.g., UUID, str)
#                 if id_type is not None and not isinstance(id_type, TypeVar):
#                     collected_id_types.add((base, id_type))
#
#         concrete_id_types = {x[1] for x in collected_id_types}
#         if len({x[1] for x in collected_id_types}) > 1:
#             msg = (
#                 f"Conflicting originator ID types detected in bases of "
#                 f"'{cls.__qualname__}': {collected_id_types}"
#             )
#             raise TypeError(msg)
#
#         # 2. RESOLVE AND ASSIGN ID TYPE
#         if "originator_id_type" not in cls.__dict__:
#             if concrete_id_types:
#                 originator_id_type = next(iter(concrete_id_types))
#             else:
#                 type_args = resolve_multi_generic_target(cls, HasOriginatorIDVersion)
#                 assert len(type_args) == 1, type_args
#                 originator_id_type = type_args[0]
#
#             if unwrap_new_type(originator_id_type) in (UUID, str, None):
#                 cls.originator_id_type = originator_id_type
#             else:
#                 msg = f"Aggregate ID type arg cannot be {originator_id_type}"
#                 raise TypeError(msg)
#
#
# class CanMutateAggregate(HasOriginatorIDVersion[TAggregateID]):
#     """Implements a :py:func:`~eventsourcing.domain.CanMutateAggregate.mutate`
#     method that evolves the state of an aggregate.
#     """
#
#     # TODO: Move this to a HasTimestamp? Why is it here??
#     timestamp: datetime
#     """Timezone-aware :class:`datetime` object representing when an event occurred."""
#     # TODO: Move this to a HasMetadata? Why is it here??
#     metadata: dict[str, str]
#     """Event metadata."""
#     event_id: UUID
#     """Event identifier."""
#
#     def mutate(self, aggregate: TAggregate | None) -> TAggregate | None:
#         """Validates and adjusts the attributes of the given ``aggregate``
#          argument. The argument is typed as ``Optional``, but the value is
#          expected to be not ``None``.
#
#         Validates the ``aggregate`` argument by checking the event's
#         :py:attr:`~eventsourcing.domain.HasOriginatorIDVersion.originator_id` equals the
#         ``aggregate``'s :py:attr:`~eventsourcing.domain.Aggregate.id`, and the event's
#         :py:attr:`~eventsourcing.domain.HasOriginatorIDVersion.originator_version` is
#         one greater than the ``aggregate``'s current
#         :py:attr:`~eventsourcing.domain.Aggregate.version`.
#         If the ``aggregate`` argument is not valid, an exception is raised.
#
#         If the ``aggregate`` argument is valid, the
#         :func:`~eventsourcing.domain.CanMutateAggregate.apply` method is called, and
#         then :py:attr:`~eventsourcing.domain.HasOriginatorIDVersion.originator_id` is
#         assigned to the aggregate's :py:attr:`~eventsourcing.domain.Aggregate.version`
#         attribute, and the ``timestamp`` is assigned to the aggregate's
#         :py:attr:`~eventsourcing.domain.Aggregate.modified_on` attribute.
#         """
#         assert aggregate is not None
#
#         if not hasattr(aggregate, "id"):
#             self_dict = self._as_dict()
#             base_kwargs = filter_kwargs_for_method_params(
#                 self_dict, type(aggregate).__base_init__
#             )
#
#             # Call the base class init method (so we don't need to always write
#             # a call to super().__init__() in every aggregate __init__() method).
#             aggregate.__base_init__(**base_kwargs)
#
#             # Pick out event attributes for aggregate subclass class init method.
#             init_kwargs = filter_kwargs_for_method_params(
#                 self_dict, type(aggregate).__init__
#             )
#
#             # Provide the aggregate id, if the __init__ method expects it.
#             if type(aggregate) in _init_mentions_id:
#                 init_kwargs["id"] = self_dict["originator_id"]
#
#             # Call the aggregate subclass class init method.
#             aggregate.__init__(**init_kwargs)  # type: ignore[misc]
#
#         # Check this event belongs to this aggregate.
#         else:
#             if self.originator_id != aggregate.id:
#                 raise OriginatorIDError(self.originator_id, aggregate.id)
#
#             # Check this event is the next in its sequence.
#             next_version = aggregate.version + 1
#             if self.originator_version != next_version:
#                 raise OriginatorVersionError(self.originator_version, next_version)
#
#         # Call apply() before mutating values, in case exception is raised.
#         self.apply(aggregate)
#
#         # Update the aggregate's 'version' number.
#         aggregate.version = self.originator_version
#
#         # Update the aggregate's 'modified on' time.
#         aggregate.modified_on = self.timestamp
#
#         # Return the mutated aggregate.
#         return aggregate
#
#     def apply(self, aggregate: Any) -> None:
#         """Applies the domain event to its aggregate.
#
#         This method does nothing but exist to be
#         overridden as a convenient way for users
#         to define how an event evolves the state
#         of an aggregate.
#         """
#
#     def _as_dict(self) -> dict[str, Any]:
#         return vars(self)
#
#
# class CanInitAggregate(CanMutateAggregate[TAggregateID]):
#     """Implements a :func:`~eventsourcing.domain.CanMutateAggregate.mutate`
#     method that constructs the initial state of an aggregate.
#     """
#
#
# class MetaDomainEvent(EventsourcingType):
#     """Metaclass which ensures all domain event classes are frozen dataclasses."""
#
#     def __new__(
#         cls, name: str, bases: tuple[type[TDomainEvent], ...], cls_dict: dict[str, Any]
#     ) -> type[TDomainEvent]:
#         event_cls = cast(
#             "type[TDomainEvent]", super().__new__(cls, name, bases, cls_dict)
#         )
#         event_cls = dataclasses.dataclass(frozen=True, kw_only=True)(event_cls)
#         event_cls.__signature__ = inspect.signature(event_cls.__init__)  # type: ignore[attr-defined]
#         return event_cls
#
#
# @dataclass(frozen=True, kw_only=True)
# class DomainEvent(metaclass=MetaDomainEvent):
#     """Frozen data class representing domain model events."""
#
#     originator_id: UUID
#     """UUID identifying an aggregate to which the event belongs."""
#     originator_version: int
#     """Integer identifying the version of the aggregate when the event occurred."""
#     timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
#     """Timezone-aware :class:`datetime` object representing when an event occurred."""
#     metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
#     """Domain event metadata."""
#     event_id: UUID = NIL_UUID
#     """Domain event identifier."""
#
#     def __post_init__(self) -> None:
#         if not isinstance(self.originator_id, UUID):
#             msg = (
#                 f"{type(self)} "
#                 f"was initialized with a non-UUID originator_id: "
#                 f"{self.originator_id!r}"
#             )
#             raise TypeError(msg)
#         # Support legacy databases by constructing a version 5 UUID.
#         if self.event_id == NIL_UUID:
#             deterministic_id = event_id_from_originator_id_and_version(
#                 self.originator_id,
#                 self.originator_version,
#             )
#             object.__setattr__(self, "event_id", deterministic_id)
#
#
# @dataclass(frozen=True, kw_only=True)
# class GenericDomainEvent(
#     HasOriginatorIDVersion[TAggregateID], metaclass=MetaDomainEvent
# ):
#     """Frozen data class representing domain model events."""
#
#     originator_id: TAggregateID
#     """Identifies the aggregate to which the event belongs."""
#     originator_version: int
#     """Integer identifying the version of the aggregate when the event occurred."""
#     timestamp: datetime = field(default_factory=datetime_now_with_tzinfo)
#     """Timezone-aware :class:`datetime` object representing when an event occurred."""
#     metadata: dict[str, str] = field(default_factory=get_metadata_from_context)
#     """Domain event metadata."""
#     event_id: UUID = NIL_UUID
#     """Domain event identifier."""
#
#     def __post_init__(self) -> None:
#         assert type(self).originator_id_type is not None
#         if not isinstance(
#             self.originator_id, unwrap_new_type(type(self).originator_id_type)
#         ):
#             msg = (
#                 f"{type(self).__qualname__} was initialized with a "
#                 f"{type(self.originator_id)}, expected "
#                 f"{type(self).originator_id_type}"
#             )
#             raise TypeError(msg)
#         # Support legacy databases by constructing a version 5 UUID for `event_id`.
#         if self.event_id == NIL_UUID:
#             deterministic_id = event_id_from_originator_id_and_version(
#                 self.originator_id,
#                 self.originator_version,
#             )
#             object.__setattr__(self, "event_id", deterministic_id)
#
#
# @dataclass(frozen=True)
# class AggregateEvent(CanMutateAggregate[UUID], DomainEvent):
#     """Frozen data class representing aggregate events.
#
#     Subclasses represent original decisions made by domain model aggregates.
#     """
#
#
# @dataclass(frozen=True)
# class GenericAggregateEvent(
#     CanMutateAggregate[TAggregateID], GenericDomainEvent[TAggregateID]
# ):
#     """Frozen data class representing aggregate events.
#
#     Subclasses represent original decisions made by domain model aggregates.
#     """
#
#
# @dataclass(frozen=True, kw_only=True)
# class AggregateCreated(CanInitAggregate[UUID], AggregateEvent):
#     """Frozen data class representing the initial creation of an aggregate."""
#
#
# @dataclass(frozen=True, kw_only=True)
# class GenericAggregateCreated(
#     CanInitAggregate[TAggregateID], GenericAggregateEvent[TAggregateID]
# ):
#     """Frozen data class representing the initial creation of an aggregate."""
#
#
# class LogEvent(DomainEvent):
#     """Deprecated: Inherit from DomainEvent instead.
#
#     Base class for the events of event-sourced logs.
#     """
#
#
# if TYPE_CHECKING:
#     pass
#
#
# @overload
# def event(arg: TDecoratableType, /) -> TDecoratableType:
#     """Signature for calling ``@event`` decorator with decorated method."""
#
#
# @overload
# def event(
#     arg: type[CanMutateAggregate[Any] | AbstractDecision], /
# ) -> Callable[[TDecoratableType], TDecoratableType]:
#     """Signature for calling ``@event`` decorator with event class."""
#
#
# @overload
# def event(
#     arg: str, /, *, topic: str | None = None
# ) -> Callable[[TDecoratableType], TDecoratableType]:
#     """Signature for calling ``@event`` decorator with event name."""
#
#
# @overload
# def event(arg: None = None, /) -> Callable[[TDecoratableType], TDecoratableType]:
#     """Signature for calling ``@event`` decorator without event specification."""
#
#
# class AbstractDecoratedFuncCaller:
#     pass
#
#
# class DecoratedFuncCaller(
#     CanMutateAggregate[TAggregateID], AbstractDecoratedFuncCaller
# ):
#     def apply(self, aggregate: BaseAggregate[TAggregateID]) -> None:
#         """Applies event to aggregate by calling method decorated by @event."""
#         # Identify the function that was decorated.
#         decorated_func = decorated_funcs[type(self)]
#
#         # Select event attributes mentioned in function signature.
#         self_dict = self._as_dict()
#         kwargs = filter_kwargs_for_method_params(self_dict, decorated_func)
#
#         # Call the original method with event attribute values.
#         decorated_method = decorated_func.__get__(aggregate, type(aggregate))
#         decorated_method(**kwargs)
#
#         # Call super method, just in case any base classes need it.
#         super().apply(aggregate)
#
#
# # This helps enforce single usage of original event classes in decorators.
#
# # This keeps track of the "created" event classes for an aggregate.
# _initial_event_classes: dict[type, list[type[CanMutateAggregate[Any]]]] = {}
#
# # This remembers which event class to trigger when a decorated method is called.
#
# # This remembers which decorated func a decorated func caller should call.
# decorated_funcs: dict[type, CallableType] = {}
#
# # This keeps track of decorators on "non-command" projection-only methods.
#
#
# _annotations_mention_id: set[type[BaseAggregate[Any]]] = set()
# _init_mentions_id: set[type[BaseAggregate[Any]]] = set()
# _create_id_param_names: dict[type[BaseAggregate[Any]], list[str]] = defaultdict(list)
#
# ENVVAR_DISABLE_REDEFINITION_CHECK = "EVENTSOURCING_DISABLE_REDEFINITION_CHECK"
#
#
# class MetaAggregate(EventsourcingType, ABCMeta, Generic[TAggregate]):
#     """Metaclass for aggregate classes."""
#
#     def __call__(
#         cls: MetaAggregate[TAggregate], *args: Any, **kwargs: Any
#     ) -> TAggregate:
#         if cls is BaseAggregate:
#             msg = "Please define or use subclasses of BaseAggregate."
#             raise TypeError(msg)
#         created_event_classes = _initial_event_classes[cls]
#         # Here, unlike when calling _create(), we don't have a given event class,
#         # so we need to check that there is one "created" event class to use here.
#         # We don't check this in __init_subclass__ to allow for alternatives that
#         # can be selected by developers by calling _create(event_class=...).
#         if len(created_event_classes) == 0:
#             msg = f"No \"created\" event classes defined on class '{cls.__name__}'."
#             raise TypeError(msg)
#
#         if len(created_event_classes) > 1:
#             msg = (
#                 f"{cls.__qualname__} can't decide which of many "
#                 '"created" event classes to use: '
#                 f"""'{"', '".join(c.__name__ for c in created_event_classes)}'. """
#                 "Please use class arg 'created_event_name' or"
#                 " @event decorator on __init__ method."
#             )
#             raise TypeError(msg)
#
#         kwargs = _coerce_args_to_kwargs(
#             cls.__init__,  # type: ignore[misc]
#             args,
#             kwargs,
#             expects_id=cls in _annotations_mention_id,
#         )
#         return cls._create(
#             event_class=created_event_classes[0],
#             **kwargs,
#         )
#
#     def _create(
#         cls: MetaAggregate[TAggregate],
#         event_class: type[CanInitAggregate[Any]],
#         **kwargs: Any,
#     ) -> TAggregate:
#         # Just define method signature for the __call__() method.
#         raise NotImplementedError  # pragma: no cover
#
#
# def _fill_and_validate_id_type(
#     cls: type[BaseAggregate[Any]],
#     event_cls: type[HasOriginatorIDVersion[Any]],
# ) -> type | GenericAlias:
#     filled_event_cls = _fill_id_type(cls, event_cls)
#     _validate_id_type(cls, filled_event_cls)
#     return filled_event_cls
#
#
# def _fill_id_type(
#     cls: type[BaseAggregate[Any]],
#     event_cls: Any,  # Relaxed to accept type | GenericAlias
# ) -> Any:
#     # 1. Extract the raw origin class to perform structural checks safely
#     origin = safe_get_origin(event_cls)
#     is_already_alias = origin is not None
#
#     if not is_already_alias:
#         origin = event_cls
#
#     assert isinstance(
#         origin, type
#     ), f"Expected type or generic alias, got {type(event_cls)}"
#
#     # 2. Extract remaining open parameters
#     params = safe_get_params(event_cls)
#     if not params:
#         return event_cls
#
#     # 3. Swap TAggregateID for the concrete type, leave others as unresolved TypeVars
#     args = [cls.originator_id_type if p == TAggregateID else p for p in params]
#
#     # 4. Optimization & Normalization
#     if tuple(args) == tuple(params) and is_already_alias:
#         # It came in as a GenericAlias, it can leave as one safely.
#         return event_cls
#         # If it came in as a raw class, we fall through to subscript it
#         # to make it an "open" generic alias (e.g., Something -> Something[T])
#
#     # 5. Subscript the class or alias with the new arguments
#     callable_event_cls: Any = event_cls
#     return callable_event_cls[*args]
#
#
# def _validate_id_type(
#     cls: type[BaseAggregate[Any]],
#     event_cls: type[HasOriginatorIDVersion[Any]] | GenericAlias,
# ) -> None:
#     if not _is_valid_id_type(
#         _get_originator_type_id(event_cls), _get_originator_type_id(cls)
#     ):
#         msg = (
#             f"Invalid originator ID type: "
#             f"{event_cls} has {event_cls.originator_id_type}, "
#             f"{cls} expects {cls.originator_id_type}"
#         )
#         raise TypeError(msg) from None
#
#
# def _is_valid_id_type(id_type: Any, must_match: Any = None) -> bool:
#     if id_type and must_match:
#         return unwrap_new_type(id_type) is unwrap_new_type(must_match)
#     # Check the originator ID type is acceptable.
#     # - accept None, UUID, or str types.
#     id_type = unwrap_new_type(id_type)
#     return id_type is None or (
#         isinstance(id_type, type)
#         and (issubclass(id_type, UUID) or issubclass(id_type, str))
#     )
#
#
# def diagnose_mro_conflict(name: str, bases: Iterable[Any]) -> str:
#     """
#     Analyzes a collection of base classes to
#     identify why Python cannot construct an MRO.
#     """
#     # Resolve generic aliases to their underlying raw types
#     resolved_bases: list[type] = [
#         typing.get_origin(b) or b
#         for b in bases
#         if isinstance(b, type) or typing.get_origin(b) is not None
#     ]
#
#     lines: list[str] = []
#     lines.append(f"🔍 Analyzing MRO consistency for bases of {name}:")
#     lines.extend(
#         f"   - {resolved_base.__qualname__}" for resolved_base in resolved_bases
#     )
#
#     # 1. Gather all individual MRO sequences that must be merged
#     sequences: list[list[type]] = [list(base.__mro__) for base in resolved_bases]
#     sequences.append(list(resolved_bases))  # The local tracking sequence
#
#     # 2. Extract directional constraints: Class X must come BEFORE Class Y
#     # Represented as: dependencies[X] = set(Y1, Y2...) meaning X < Y
#     dependencies: dict[type, set[type]] = defaultdict(set)
#     reasons: dict[tuple[type, type], str] = {}  # Tracks why a constraint exists
#
#     for seq in sequences:
#         for i in range(len(seq)):
#             for j in range(i + 1, len(seq)):
#                 u, v = seq[i], seq[j]
#                 dependencies[u].add(v)
#                 if (u, v) not in reasons:
#                     # Remember if it came from a parent's MRO
#                     # or the local definition order
#                     if seq == resolved_bases:
#                         reasons[(u, v)] = (
#                             f"Local definition order: {u.__name__} was "
#                             f"listed before {v.__name__}"
#                         )
#                     else:
#                         reasons[(u, v)] = f"Inherited from {seq[0].__name__}'s MRO tree"
#
#     # 3. Detect Cycles (Contradictions) using a simple cycle detector
#     def find_cycle(
#         node: type, visited: set[type], stack: set[type], path: list[type]
#     ) -> bool:
#         visited.add(node)
#         stack.add(node)
#         path.append(node)
#
#         for neighbor in dependencies[node]:
#             if neighbor in stack:
#                 path.append(neighbor)
#                 return True
#             if neighbor not in visited and find_cycle(neighbor, visited, stack, path):
#                 return True
#
#         stack.remove(node)
#         path.pop()
#         return False
#
#     visited: set[type] = set()
#     stack: set[type] = set()
#     cycle_path: list[type] = []
#     has_conflict = False
#
#     for node in list(dependencies.keys()):
#         if node not in visited and find_cycle(node, visited, stack, cycle_path):
#             has_conflict = True
#             break
#
#     # 4. Report the findings
#     if not has_conflict:
#         lines.append(
#             "✅ No structural conflicts found! Python should be able "
#             "to linearize these bases successfully."
#         )
#     else:
#         # Isolate the breaking loop
#         conflict_loop = cycle_path[cycle_path.index(cycle_path[-1]) :]
#
#         lines.append("❌ CONFLICT DETECTED: A cyclical ordering contradiction exists!")
#         lines.append(
#             "-----------------------------------------------------------------"
#         )
#         lines.append("The following loop of dependencies cannot be satisfied:")
#
#         for i in range(len(conflict_loop) - 1):
#             u = conflict_loop[i]
#             v = conflict_loop[i + 1]
#             reason = reasons.get((u, v), "Inferred hierarchy constraint")
#             lines.append(f"  👉 {u.__qualname__} must precede {v.__qualname__}")
#             lines.append(f"     Reason: {reason}\n")
#
#         lines.append("💡 HOW TO FIX IT:")
#         lines.append(
#             "Review the reasons listed above. You likely need to change the order "
#         )
#         lines.append(
#             "of the base classes in your definition line, or remove a redundant layout."
#         )
#
#     return "\n".join(lines)
#
#
# class BaseAggregate(Generic[TAggregateID], metaclass=MetaAggregate):
#     """Base class for aggregates."""
#
#     INITIAL_VERSION: int = 1
#
#     originator_id_type: ClassVar[type[UUID | str] | None] = UUID
#
#     @staticmethod
#     def create_id(*_: Any, **__: Any) -> TAggregateID:
#         """Returns a new aggregate ID."""
#         raise NotImplementedError
#
#     @classmethod
#     def _create(
#         cls: type[Self],
#         event_class: type[CanInitAggregate[TAggregateID]],
#         *,
#         id: TAggregateID | None = None,  # noqa: A002
#         **kwargs: Any,
#     ) -> Self:
#         """Constructs a new aggregate object instance."""
#         if getattr(cls, "TOPIC", None):
#             _check_explicit_topic_is_registered(event_class)
#
#         # Construct the domain event with an ID and a
#         # version, and a topic for the aggregate class.
#         create_id_kwargs = {
#             k: v for k, v in kwargs.items() if k in _create_id_param_names[cls]
#         }
#         if id is not None:
#             originator_id = id
#             if not isinstance(originator_id, (UUID, str)):
#                 msg = f"Given id was not a UUID or str: {originator_id!r}"
#                 raise TypeError(msg)
#         else:
#             try:
#                 originator_id = cls.create_id(**create_id_kwargs)
#             except NotImplementedError as e:
#                 msg = f"Please pass an 'id' arg or define a create_id() method on {cls}"
#                 raise NotImplementedError(msg) from e
#
#             if cls.originator_id_type and not isinstance(
#                 originator_id, unwrap_new_type(cls.originator_id_type)
#             ):
#                 msg = (
#                     f"{cls.create_id.__module__}.{cls.create_id.__qualname__}"
#                     f" did not return a {cls.originator_id_type.__qualname__}, "
#                     f"it returned: {originator_id!r}"
#                 )
#                 raise TypeError(msg)
#
#         # Impose the required common "created" event attribute values.
#         kwargs = kwargs.copy()
#         kwargs.update(
#             originator_id=originator_id,
#             event_id=uuid4(),
#             originator_version=cls.INITIAL_VERSION,
#         )
#
#         if "timestamp" in kwargs and kwargs["timestamp"] is None:
#             kwargs["timestamp"] = datetime_now_with_tzinfo()
#
#         try:
#             created_event = event_class(**kwargs)
#         except TypeError as e:
#             msg = f"Unable to construct '{event_class.__qualname__}' event: {e}"
#             raise TypeError(msg) from e
#         # Construct the aggregate object.
#         agg = cls.__new__(cls)
#         agg = created_event.mutate(agg)
#
#         assert agg is not None
#         # Append the domain event to pending list.
#         agg.pending_events.append(created_event)
#         # Return the aggregate.
#         return agg
#
#     def __base_init__(
#         self,
#         originator_id: Any,
#         originator_version: int,
#         timestamp: datetime,
#     ) -> None:
#         """Initialises an aggregate object with an :data:`id`, a :data:`version`
#         number, and a :data:`timestamp`.
#         """
#         self._id: TAggregateID = originator_id
#         self._version = originator_version
#         self._created_on = timestamp
#         self._modified_on = timestamp
#         self._pending_events: list[CanMutateAggregate[TAggregateID]] = []
#
#     @property
#     def id(self) -> TAggregateID:
#         """The ID of the aggregate."""
#         return self._id
#
#     @property
#     def version(self) -> int:
#         """The version number of the aggregate."""
#         return self._version
#
#     @version.setter
#     def version(self, version: int) -> None:
#         self._version = version
#
#     @property
#     def created_on(self) -> datetime:
#         """The date and time when the aggregate was created."""
#         return self._created_on
#
#     @property
#     def modified_on(self) -> datetime:
#         """The date and time when the aggregate was last modified."""
#         return self._modified_on
#
#     @modified_on.setter
#     def modified_on(self, modified_on: datetime) -> None:
#         self._modified_on = modified_on
#
#     @property
#     def pending_events(self) -> list[CanMutateAggregate[TAggregateID]]:
#         """A list of pending events."""
#         return self._pending_events
#
#     def trigger_event(
#         self,
#         event_class: type[CanMutateAggregate[TAggregateID]],
#         **kwargs: Any,
#     ) -> None:
#         """Triggers domain event of given type, by creating
#         an event object and using it to mutate the aggregate.
#         """
#         if getattr(type(self), "TOPIC", None):
#             if event_class.__name__ == "Event":
#                 msg = "Triggering base 'Event' class is prohibited."
#                 raise ProgrammingError(msg)
#             _check_explicit_topic_is_registered(event_class)
#
#         # Construct the domain event as the
#         # next in the aggregate's sequence.
#         # Use counting to generate the sequence.
#         next_version = self.version + 1
#
#         # Impose the required common domain event attribute values.
#         kwargs = kwargs.copy()
#         kwargs.update(
#             originator_id=self.id,
#             originator_version=next_version,
#             event_id=uuid4(),
#         )
#         if "timestamp" in kwargs and kwargs["timestamp"] is None:
#             kwargs["timestamp"] = datetime_now_with_tzinfo()
#
#         try:
#             new_event = event_class(**kwargs)
#         except TypeError as e:
#             msg = f"Can't construct event {event_class}: {e}"
#             raise TypeError(msg) from None
#
#         # Mutate aggregate with domain event.
#         new_event.mutate(self)
#         # Append the domain event to pending list.
#         self._pending_events.append(new_event)
#
#     def collect_events(self) -> Sequence[CanMutateAggregate[TAggregateID]]:
#         """Collects and returns a list of pending aggregate
#         :class:`AggregateEvent` objects.
#         """
#         collected = []
#         while self._pending_events:
#             collected.append(self._pending_events.pop(0))
#         return collected
#
#     def __eq__(self, other: object) -> bool:
#         return type(self) is type(other) and self.__dict__ == other.__dict__
#
#     def __repr__(self) -> str:
#         attrs = [
#             f"{k.lstrip('_')}={v!r}"
#             for k, v in self.__dict__.items()
#             if k != "_pending_events"
#         ]
#         return f"{type(self).__name__}({', '.join(attrs)})"
#
#     def __init_subclass__(cls: type[BaseAggregate[TAggregateID]]) -> None:
#         """
#         Initialises aggregate subclass by defining __init__ method and event classes.
#         """
#         super().__init_subclass__()
#
#         # Find the type arg for TAggregateID.
#         assert "originator_id_type" not in cls.__dict__
#         type_args = resolve_multi_generic_target(cls, BaseAggregate)
#         assert len(type_args) == 1, type_args
#         resolved_originator_id_type = type_args[0]
#
#         if not _is_valid_id_type(resolved_originator_id_type):
#             msg = f"Aggregate ID type arg cannot be {resolved_originator_id_type}"
#             raise TypeError(msg)
#
#         cls.originator_id_type = resolved_originator_id_type
#
#         # Ensure we aren't defining another instance of the same class,
#         # because annotations can get confused when using singledispatchmethod
#         # during class definition e.g. on an aggregate projector function.
#         _module = importlib.import_module(cls.__module__)
#         if (
#             cls.__name__ in _module.__dict__
#             and ENVVAR_DISABLE_REDEFINITION_CHECK not in os.environ
#         ):
#             msg = (
#                 f"Name '{cls.__name__}' of {cls} already defined in "
#                 f"'{cls.__module__}' module: {_module.__dict__[cls.__name__]}"
#             )
#             raise ProgrammingError(msg)
#
#         # Get the class annotations.
#         class_annotations = cls.__dict__.get("__annotations__", {})
#         try:
#             class_annotations.pop("id")
#             # Remember if annotations mention 'id'.
#             _annotations_mention_id.add(cls)
#         except KeyError:
#             pass
#
#         if "id" in cls.__dict__:
#             msg = f"Setting attribute 'id' on class '{cls.__name__}' is not allowed"
#             raise ProgrammingError(msg)
#
#         # Process the class as a dataclass, if there are annotations.
#         if (
#             class_annotations
#             or cls in _annotations_mention_id
#             or any(dataclasses.is_dataclass(base) for base in cls.__bases__)
#         ):
#             dataclasses.dataclass(eq=False, repr=False)(cls)
#
#         # TODO: Not fully sure why we apparently define an __init__ method without
#         #   an 'id' parameter but then later will pass an 'id' argument if we just
#         #   stripped it from the annotations. Identify what this supports and explain
#         #   it here...
#
#         # Remember if __init__ mentions ID.
#         for param_name in inspect.signature(cls.__init__).parameters:
#             if param_name == "id":
#                 _init_mentions_id.add(cls)
#                 break
#
#         # Identify or define a base event class for this aggregate.
#         base_event_name = "Event"
#         base_event_cls: type[CanMutateAggregate[TAggregateID]] | None = None
#         msg = f"Base event class 'Event' not defined on {cls} or ancestors"
#         base_event_class_not_defined_error = TypeError(msg)
#
#         try:
#             base_event_cls = cls.__dict__[base_event_name]
#
#             # Check the base event class is the right sort of thing.
#             if not _is_sub_canmutateaggregate(base_event_cls):
#                 msg = (
#                     f"Expected '{base_event_name}' on {cls.__module__}."
#                     f"{cls.__qualname__} to derive from CanMutateAggregate, got "
#                     f"{base_event_cls} instead"
#                 )
#                 raise TypeError(msg)
#             _validate_id_type(cls, base_event_cls)
#
#         except KeyError:
#             try:
#                 super_base_event_cls = getattr(cls, base_event_name)
#             except AttributeError:
#                 # Defer raising an error until we know we need a base event class.
#                 pass
#             else:
#                 base_event_cls = cls._define_event_class(
#                     name=base_event_name,
#                     bases=(_fill_and_validate_id_type(cls, super_base_event_cls),),
#                     apply_method=None,
#                 )
#                 _validate_id_type(cls, base_event_cls)
#                 setattr(cls, base_event_name, base_event_cls)
#
#         # Analyse __init__ attribute, to get __init__ method and @event decorator.
#         init_attr: FunctionType | CommandMethodDecorator | None = cls.__dict__.get(
#             "__init__"
#         )
#         if init_attr is None:
#             # No method, no decorator.
#             init_method: CallableType | None = None
#             init_decorator: CommandMethodDecorator | None = None
#         elif isinstance(init_attr, CommandMethodDecorator):
#             # Method decorated with @event.
#             init_method = init_attr.decorated_func
#             init_decorator = init_attr
#         else:
#             # Undecorated __init__ method.
#             init_decorator = None
#             init_method = init_attr
#
#         # Remember which events have been redefined, to preserve apparent hierarchy,
#         # in a mapping from the original class to the redefined class.
#         redefined_event_classes: dict[
#             type[CanMutateAggregate[TAggregateID]],
#             type[CanMutateAggregate[TAggregateID]],
#         ] = {}
#
#         # Identify or define the aggregate's initial event class.
#         initial_event_class: type[CanMutateAggregate[TAggregateID]] | None = None
#         initial_event_topic: str | None = None
#         initial_event_name = ""
#
#         # Analyse __init__ method decorator.
#         if init_decorator:
#
#             # Does the decorator specify an event class?
#             if init_decorator.given_event_cls:
#
#                 # Check the event class is the right sort of thing.
#                 if not _is_sub_canmutateaggregate(init_decorator.given_event_cls):
#                     msg = (
#                         f"class '{init_decorator.given_event_cls}' "
#                         f"does not derive from CanMutateAggregate"
#                     )
#                     raise TypeError(msg)
#
#                 initial_event_class = cast(
#                     type[CanMutateAggregate[TAggregateID]],
#                     init_decorator.given_event_cls,
#                 )
#
#             # No given event class. Does the decorator specify an event name?
#             elif init_decorator.event_cls_name:
#                 initial_event_topic = init_decorator.event_topic
#
#                 initial_event_name = init_decorator.event_cls_name
#
#             # Disallow using decorator on __init__ without event name or class.
#             else:
#                 msg = "@event decorator on __init__ has neither event name nor class"
#                 raise TypeError(msg)
#
#         # Do we need to define a created event class?
#         base_initial_event_class: type[CanMutateAggregate[TAggregateID]] | None = None
#         if not initial_event_class:
#             # Decide the base "created" event class.
#             if initial_event_name:
#                 # Look for a base class with the same name.
#                 with contextlib.suppress(AttributeError):
#                     initial_event_class = getattr(cls, initial_event_name)
#
#             if initial_event_class is None:
#                 # Look for base class with one nominated "created" event.
#                 for base_cls in cls.__mro__:
#                     if (
#                         base_cls in _initial_event_classes
#                         and len(_initial_event_classes[base_cls]) == 1
#                     ):
#                         base_initial_event_class = _initial_event_classes[base_cls][0]
#                         break
#
#             if base_initial_event_class:
#                 if not initial_event_name:
#                     initial_event_name = base_initial_event_class.__name__
#
#                     # Look for synonymous event class on this class.
#                     base_initial_event_class = getattr(cls, initial_event_name)
#
#                 # Disallow init method from having variable params, because
#                 # we will using it to define an initial event class.
#                 if init_method:
#                     _raise_type_error_if_func_has_variable_params(init_method)
#
#             elif initial_event_name:
#                 msg = (
#                     "Can't define initial event class "
#                     f"for name '{initial_event_name}': unable "
#                     f"to locate a suitable base class. Please "
#                     "derive a suitable class from CanMutateAggregate."
#                 )
#                 raise TypeError(msg)
#             else:
#                 # We just aren't in the business of defining an initial event class.
#                 assert not initial_event_name
#                 assert not initial_event_class
#                 assert not base_initial_event_class
#
#         decorators_needing_function_callers: dict[str, CommandMethodDecorator] = {}
#
#         # Find and analyse any @event decorators.
#         for attr_name, attr_value in tuple(cls.__dict__.items()):
#             event_decorator: CommandMethodDecorator | None = None
#
#             # Ignore a decorator on the __init__ method.
#             if isinstance(attr_value, CommandMethodDecorator) and (
#                 attr_value.decorated_func.__name__ == "__init__"
#             ):
#                 continue
#
#             # Handle @property.setter decorator on top of @event decorator.
#             if isinstance(attr_value, property) and isinstance(
#                 attr_value.fset, CommandMethodDecorator
#             ):
#                 event_decorator = attr_value.fset
#                 # Inspect the setter method.
#                 method_signature = inspect.signature(event_decorator.decorated_func)
#                 assert len(method_signature.parameters) == 2
#                 event_decorator.is_property_setter = True
#                 event_decorator.property_setter_arg_name = list(
#                     method_signature.parameters
#                 )[1]
#                 if event_decorator.decorated_func.__name__ != attr_name:
#                     attr = cls.__dict__[event_decorator.decorated_func.__name__]
#                     if isinstance(attr, CommandMethodDecorator):
#                         # This is the "x = property(getx, setx) form" where setx
#                         # is a decorated method.
#                         continue
#                         # Otherwise, it's "x = property(getx, event(setx))".
#                 elif event_decorator.is_name_inferred_from_method:
#                     # This is the "@property.setter \ @event" form. We don't want
#                     # event class name inferred from property (not past participle).
#                     method_name = event_decorator.decorated_func.__name__
#                     msg = (
#                         f"@event decorator under @{method_name}.setter "
#                         "requires event name or class"
#                     )
#                     raise TypeError(msg)
#
#             elif isinstance(attr_value, CommandMethodDecorator):
#                 event_decorator = attr_value
#
#             if event_decorator is not None:
#                 if event_decorator.given_event_cls:
#                     given = event_decorator.given_event_cls
#                     # Check the event class is the right sort of thing.
#                     if not _is_sub_canmutateaggregate(given):
#                         msg = (
#                             f"{event_decorator.given_event_cls} "
#                             f"is not subclass of {CanMutateAggregate.__name__}"
#                         )
#                         raise TypeError(msg)
#
#                     # Check this event class name is an attribute of aggregate cls.
#                     if not hasattr(cls, given.__name__):
#                         # TODO: Allow this by keeping track of use (like in dcb module).
#                         msg = (
#                             "Event classes given in @event decorators must be "
#                             f"attributes of the aggregate class: {given}"
#                         )
#                         raise TypeError(msg)
#
#                     decorators_needing_function_callers[given.__name__] = (
#                         event_decorator
#                     )
#
#                 else:
#                     # Check event class isn't already defined.
#                     assert event_decorator.event_cls_name
#                     if (
#                         event_decorator.event_cls_name in cls.__dict__
#                         or event_decorator.event_cls_name
#                         in decorators_needing_function_callers
#                     ):
#                         msg = (
#                             f"{event_decorator.event_cls_name} "
#                             f"event already defined on {cls.__name__}"
#                         )
#                         raise TypeError(msg)
#
#                     decorators_needing_function_callers[
#                         event_decorator.event_cls_name
#                     ] = event_decorator
#
#         # Check any create_id() method defined on this class is static or class method.
#         if "create_id" in cls.__dict__ and not isinstance(
#             cls.__dict__["create_id"], (staticmethod, classmethod)
#         ):
#             msg = (
#                 f"{cls.create_id} is not a static or class method: "
#                 f"{type(cls.create_id)}"
#             )
#             raise TypeError(msg)
#
#         # Get the parameters of the create_id method that will be used by this class.
#         for name, param in inspect.signature(cls.create_id).parameters.items():
#             if param.kind in [param.KEYWORD_ONLY, param.POSITIONAL_OR_KEYWORD]:
#                 _create_id_param_names[cls].append(name)
#
#         # Find all events visible as attributes on this class.
#         all_visible_event_classes: dict[str, type[HasOriginatorIDVersion[Any]]] = {}
#         for mro_cls in cls.__mro__:
#             for name, value in mro_cls.__dict__.items():
#                 if (
#                     isinstance(value, type)
#                     and issubclass(value, HasOriginatorIDVersion)
#                     and name not in all_visible_event_classes
#                 ):
#                     all_visible_event_classes[name] = value
#
#         # Ensure events that all event visible on this class are defined on this class,
#         # that all "can mutate" classes are subclasses of the base event class, and of
#         # any subclasses of any of their base event classes that we have redefined.
#         # Also ensure that all events are consistent with the "originator ID type" of
#         # this aggregate class. Fill in any classes that are missing by constructing
#         # subclasses, and fill in any missing type arguments, where the type parameter
#         # is for the "aggregate ID type".
#         for name, value in all_visible_event_classes.items():
#             # Don't subclass the base event class again.
#             if name == base_event_name:
#                 continue
#
#             # Don't subclass lowercase named attributes.
#             if name.lower() == name:
#                 continue
#
#             # Check we have a base event class.
#             if base_event_cls is None:
#                 raise base_event_class_not_defined_error
#
#             # Identify base classes that were redefined, to preserve hierarchy.
#             redefined_bases = []
#
#             # 1. Iterate over the original bases to preserve type arguments
#             for value_base in safe_get_original_bases(value):
#                 value_origin = safe_get_origin(value_base)
#                 value_args = safe_get_args(value_base)
#
#                 # 2. Determine which raw class to look for in the dict of redefineds.
#                 search_target = value_origin if value_origin is not None else value_base
#
#                 if search_target in redefined_event_classes:
#                     redefined_class = redefined_event_classes[search_target]
#
#                     # 3. If the original base had type arguments,
#                     #    re-apply them to the new class!
#                     if value_args:
#                         # If there's only one argument, unpack it to avoid tuple-
#                         # nesting issues, otherwise pass the tuple of arguments.
#                         redefined_class = (
#                             redefined_class[value_args[0]]
#                             if len(value_args) == 1
#                             else redefined_class[value_args]
#                         )
#
#                     redefined_bases.append(redefined_class)
#
#             if name in decorators_needing_function_callers:
#                 decorator = decorators_needing_function_callers.pop(name)
#                 if decorator.given_event_cls:
#                     assert decorator.given_event_cls is value, "Need to fix this more"
#                     # Define a decorated function caller.
#                     event_class_bases = cls._decide_event_class_bases(
#                         [DecoratedFuncCaller, decorator.given_event_cls],
#                         redefined_bases,
#                         base_event_cls,
#                     )
#                     event_class = cls._define_event_class(
#                         decorator.given_event_cls.__name__,
#                         event_class_bases,
#                         None,
#                     )
#                 else:
#                     # Define event class from signature of original method.
#                     assert decorator.event_cls_name
#                     event_class_bases = cls._decide_event_class_bases(
#                         [DecoratedFuncCaller, value], redefined_bases, base_event_cls
#                     )
#                     event_class = cls._define_event_class(
#                         decorator.event_cls_name,
#                         event_class_bases,
#                         decorator.decorated_func,
#                         event_topic=decorator.event_topic,
#                     )
#
#                 # Cache the decorated method for the event class to use.
#                 decorated_funcs[event_class] = decorator.decorated_func
#
#                 # Remember which event class to trigger.
#                 decorated_func_callers[decorator] = cast(
#                     type[DecoratedFuncCaller], event_class
#                 )
#
#             else:
#
#                 # Don't subclass if it's already a subclass.
#                 if issubclass(value, base_event_cls):
#                     _validate_id_type(cls, value)
#
#                     # Make sure we register the "created" event class.
#                     if value is initial_event_class:
#                         assert value is not None
#                         _initial_event_classes[cls] = [value]
#                     continue
#
#                 if value is initial_event_class:
#                     event_class_bases = cls._decide_event_class_bases(
#                         [initial_event_class], redefined_bases, base_event_cls
#                     )
#                     event_class = cast(
#                         type[CanInitAggregate[TAggregateID]],
#                         cls._define_event_class(
#                             initial_event_class.__name__,
#                             event_class_bases,
#                             None,
#                             event_topic=initial_event_topic,
#                         ),
#                     )
#                     _initial_event_classes[cls] = [event_class]
#
#                 elif name == initial_event_name:
#                     assert base_initial_event_class
#                     event_class_bases = cls._decide_event_class_bases(
#                         [base_initial_event_class], redefined_bases, base_event_cls
#                     )
#                     event_class = cast(
#                         type[CanInitAggregate[TAggregateID]],
#                         cls._define_event_class(
#                             initial_event_name,
#                             event_class_bases,
#                             init_method,
#                             event_topic=initial_event_topic,
#                         ),
#                     )
#                     _initial_event_classes[cls] = [event_class]
#
#                 elif _is_sub_cansnapshotaggregate(value):
#                     if name in cls.__dict__:
#                         # User-defined snapshot: still validate its ID type,
#                         # but don't rebuild it.
#                         _validate_id_type(cls, value)
#                         continue
#                     # Don't include base event class in bases of snapshot classes.
#                     event_class_bases = (_fill_and_validate_id_type(cls, value),)
#                     # Define event class.
#                     event_class = cls._define_event_class(name, event_class_bases, None)
#
#                 else:
#                     # Decide base classes of redefined event class: it must be
#                     # a subclass of the original class, all redefined classes that
#                     # were in its bases, and the aggregate's base event class.
#                     event_class_bases = cls._decide_event_class_bases(
#                         [value], redefined_bases, base_event_cls
#                     )
#                     # Define event class.
#                     event_class = cls._define_event_class(name, event_class_bases, None)
#
#             # Check the event class is the right sort of thing.
#             _validate_id_type(cls, event_class)
#
#             setattr(cls, name, event_class)
#
#             # Remember which events have been redefined.
#             redefined_event_classes[value] = event_class
#
#         if decorators_needing_function_callers and base_event_cls is None:
#             raise base_event_class_not_defined_error
#
#         for name, decorator in decorators_needing_function_callers.items():
#             if decorator.given_event_cls:
#                 # Define a decorated function caller.
#                 event_class_bases = cls._decide_event_class_bases(
#                     [DecoratedFuncCaller, decorator.given_event_cls],
#                     [],  # TODO: redefined_bases,
#                     base_event_cls,
#                 )
#                 event_cls = cls._define_event_class(
#                     name,
#                     event_class_bases,
#                     None,
#                 )
#             else:
#                 # Define event class from signature of original method.
#                 event_class_bases = cls._decide_event_class_bases(
#                     [DecoratedFuncCaller],
#                     [],
#                     base_event_cls,
#                 )
#                 event_cls = cls._define_event_class(
#                     name,
#                     event_class_bases,
#                     decorator.decorated_func,
#                     event_topic=decorator.event_topic,
#                 )
#
#             _validate_id_type(cls, event_cls)
#
#             # Cache the decorated method for the event class to use.
#             decorated_funcs[event_cls] = decorator.decorated_func
#
#             # Set the event class as an attribute of the aggregate class.
#             setattr(cls, name, event_cls)
#
#             # Remember which event class to trigger.
#             decorated_func_callers[decorator] = cast(
#                 type[DecoratedFuncCaller], event_cls
#             )
#
#         if cls not in _initial_event_classes:
#             # Still trying to make an initial event class.
#
#             if base_initial_event_class:
#                 # We get here if we have a name but not a class.
#                 assert initial_event_class is None
#                 assert initial_event_name is not None
#                 event_class_bases = cls._decide_event_class_bases(
#                     [base_initial_event_class],
#                     [],
#                     base_event_cls,
#                 )
#                 initial_event_class = cls._define_event_class(
#                     initial_event_name,
#                     event_class_bases,
#                     init_method,
#                     event_topic=initial_event_topic,
#                 )
#                 _validate_id_type(cls, initial_event_class)
#                 # Set the event class as an attribute of the aggregate class.
#                 setattr(cls, initial_event_name, initial_event_class)
#                 _initial_event_classes[cls] = [initial_event_class]
#
#             elif initial_event_class is not None:
#                 # We get here if we have a class.
#                 if hasattr(cls, initial_event_class.__name__):
#                     if base_event_cls is None:
#                         raise base_event_class_not_defined_error
#                     if not issubclass(initial_event_class, base_event_cls):
#                         event_class_bases = cls._decide_event_class_bases(
#                             [initial_event_class],
#                             [],  # TODO: redefined_bases
#                             base_event_cls,
#                         )
#                         initial_event_class = cls._define_event_class(
#                             initial_event_class.__name__,
#                             event_class_bases,
#                             None,
#                             event_topic=initial_event_topic,
#                         )
#                         _validate_id_type(cls, initial_event_class)
#                         # Set the event class as an attribute of the aggregate class.
#                         setattr(cls, initial_event_class.__name__, initial_event_class)
#                 else:
#                     _validate_id_type(cls, initial_event_class)
#
#                 _initial_event_classes[cls] = [initial_event_class]
#
#         if getattr(cls, "TOPIC", None):
#
#             explicit_topic = cls.__dict__.get("TOPIC", None)
#
#             if not explicit_topic:
#                 msg = f"Explicit topic not defined on {cls}"
#                 raise ProgrammingError(msg)
#
#             try:
#                 register_topic(explicit_topic, cls)
#             except TopicError:
#                 msg = (
#                     f"Explicit topic '{explicit_topic}' of {cls} "
#                     f"already registered for {resolve_topic(explicit_topic)}"
#                 )
#                 raise ProgrammingError(msg) from None
#
#             for name, obj in cls.__dict__.items():
#                 if (
#                     isinstance(obj, type)
#                     and issubclass(obj, CanMutateAggregate)
#                     and name != "Event"
#                 ):
#                     explicit_topic = getattr(obj, "TOPIC", None)
#                     if not explicit_topic:
#                         msg = f"Explicit topic not defined on {obj}"
#                         raise ProgrammingError(msg)
#                     try:
#                         register_topic(explicit_topic, obj)
#                     except TopicError:
#                         msg = (
#                             f"Explicit topic '{explicit_topic}' of {obj} "
#                             f"already registered for {resolve_topic(explicit_topic)}"
#                         )
#                         raise ProgrammingError(msg) from None
#
#     @classmethod
#     def _decide_event_class_bases(
#         cls,
#         required_bases: list[type[CanMutateAggregate[TAggregateID]]],
#         redefined_bases: list[type[CanMutateAggregate[TAggregateID]]],
#         base_event_cls: type[CanMutateAggregate[TAggregateID]],
#     ) -> tuple[type | GenericAlias, ...]:
#         included = list(required_bases)
#         included.extend(
#             redefined_base
#             for redefined_base in redefined_bases
#             if issubclass(
#                 safe_get_origin(redefined_base) or redefined_base,
#                 safe_get_origin(base_event_cls) or base_event_cls,
#             )
#         )
#         if len(included) == len(required_bases):
#             assert base_event_cls is not None
#             included.append(base_event_cls)
#         return tuple(_fill_and_validate_id_type(cls, i) for i in included)
#
#     @classmethod
#     def _define_event_class(
#         cls,
#         name: str,
#         bases: tuple[type[CanMutateAggregate[Any]] | GenericAlias, ...],
#         apply_method: CallableType | None,
#         event_topic: str | None = None,
#     ) -> type[CanMutateAggregate[Any]]:
#         # Define annotations for the event class (specs the init method).
#         annotations = {}
#         if apply_method is not None:
#             method_signature = inspect.signature(apply_method)
#             super_annotations = {}
#
#             for b in reversed(bases):
#                 actual_base = typing.get_origin(b) or b
#                 # Fallback to a tuple of just the base if __mro__ is somehow missing
#                 mro = getattr(actual_base, "__mro__", (actual_base,))
#
#                 for mro_cls in reversed(mro):
#                     # Safely get the annotations dict for this specific class in the
#                     # chain and update our running dictionary.
#                     super_annotations.update(inspect.get_annotations(mro_cls))
#
#             for param_name, param in list(method_signature.parameters.items())[1:]:
#                 # Don't define 'id' on a "created" class.
#                 if param_name == "id" and apply_method.__name__ == "__init__":
#                     continue
#                 # Don't override super class annotations, unless no default on param.
#                 if param_name not in super_annotations or param.default == param.empty:
#                     annotations[param_name] = param.annotation or "typing.Any"
#         event_cls_qualname = f"{cls.__qualname__}.{name}"
#         event_cls_dict = {
#             "__annotations__": annotations,
#             "__module__": cls.__module__,
#             "__qualname__": event_cls_qualname,
#             # FIX: Explicitly inject __orig_bases__ to prevent MRO attribute leakage
#             # from base classes that were previously parameterized.
#             "__orig_bases__": bases,
#         }
#         if event_topic:
#             event_cls_dict["TOPIC"] = event_topic
#
#         def populate_namespace(ns: dict[str, Any]) -> None:
#             ns.update(event_cls_dict)
#
#         # Create the event class object.
#         try:
#             _new_class = types.new_class(name, bases, exec_body=populate_namespace)
#         except TypeError as e:
#             if "Cannot create a consistent method resolution" in str(e):
#                 msg = diagnose_mro_conflict(name, bases)
#                 raise TypeError(msg) from e
#             raise
#         return cast("type[CanMutateAggregate[Any]]", _new_class)
#
#     def __hash__(self) -> int:
#         raise NotImplementedError  # pragma: no cover
#
#
# def _check_explicit_topic_is_registered(event_class: type[object]) -> None:
#     explicit_topic = getattr(event_class, "TOPIC", None)
#     if not explicit_topic:
#         msg = f"Explicit topic not defined on {event_class}"
#         raise ProgrammingError(msg)
#     try:
#         resolved_obj = resolve_topic(explicit_topic)
#     except TopicError:
#         msg = f"Explicit topic '{explicit_topic}' on {event_class} is not registered"
#         raise ProgrammingError(msg) from None
#     if resolved_obj is not event_class:
#         msg = (
#             f"Explicit topic '{explicit_topic}' on {event_class} "
#             f"already registered for {resolved_obj}"
#         )
#         raise ProgrammingError(msg) from None
#
#
# class OriginatorIDError(EventSourcingError):
#     """Raised when a domain event can't be applied to
#     an aggregate due to an ID mismatch indicating
#     the domain event is not in the aggregate's
#     sequence of events.
#     """
#
#
# class OriginatorVersionError(EventSourcingError):
#     """Raised when a domain event can't be applied to
#     an aggregate due to version mismatch indicating
#     the domain event is not the next in the aggregate's
#     sequence of events.
#     """
#
#
# @runtime_checkable
# class SnapshotProtocol(DomainEventProtocol[TAggregateID_co], Protocol):
#     @property
#     def state(self) -> Any:
#         """Snapshots have a read-only 'state'."""
#         raise NotImplementedError  # pragma: no cover
#
#     # TODO: Improve on this 'Any'.
#     @classmethod
#     def take(cls: Any, aggregate: Any) -> Any:
#         """Snapshots have a 'take()' class method."""
#
#
# class CanSnapshotAggregate(HasOriginatorIDVersion[TAggregateID]):
#     topic: str
#     state: Any
#
#     @classmethod
#     def take(
#         cls,
#         aggregate: MutableOrImmutableAggregate[TAggregateID],
#     ) -> Self:
#         """Creates a snapshot of the given :class:`Aggregate` object."""
#         aggregate_state = dict(vars(aggregate))
#         class_version = getattr(type(aggregate), "class_version", 1)
#         if class_version > 1:
#             aggregate_state["class_version"] = class_version
#         if isinstance(aggregate, Aggregate):
#             aggregate_state.pop("_id")
#             aggregate_state.pop("_version")
#             aggregate_state.pop("_pending_events")
#         return cls(
#             originator_id=aggregate.id,  # type: ignore[call-arg]
#             originator_version=aggregate.version,  # pyright: ignore[reportCallIssue]
#             topic=get_topic(type(aggregate)),  # pyright: ignore[reportCallIssue]
#             state=aggregate_state,  # pyright: ignore[reportCallIssue]
#         )
#
#     def mutate(self, aggregate: TAggregate | None) -> TAggregate | None:
#         """Reconstructs the snapshotted :class:`Aggregate` object."""
#         cls = cast(type[TAggregate], resolve_topic(self.topic))
#         aggregate_state = dict(self.state)
#         from_version = aggregate_state.pop("class_version", 1)
#         class_version = getattr(cls, "class_version", 1)
#         while from_version < class_version:
#             upcast_name = f"upcast_v{from_version}_v{from_version + 1}"
#             upcast = getattr(cls, upcast_name)
#             upcast(aggregate_state)
#             from_version += 1
#
#         aggregate_state["_id"] = self.originator_id
#         aggregate_state["_version"] = self.originator_version
#         aggregate_state["_pending_events"] = []
#         aggregate = object.__new__(cls)
#         object.__setattr__(aggregate, "__dict__", aggregate_state)
#         return aggregate
#
#
# @dataclass(frozen=True, kw_only=True)
# class Snapshot(CanSnapshotAggregate[UUID], DomainEvent):
#     """Snapshots represent the state of an aggregate at a particular
#     version.
#
#     Constructor arguments:
#
#     :param UUID originator_id: ID of originating aggregate.
#     :param int originator_version: version of originating aggregate.
#     :param datetime timestamp: date-time of the event
#     :param str topic: string that includes a class and its module
#     :param dict state: state of originating aggregate.
#     """
#
#     topic: str
#     state: dict[str, Any]
#
#
# @dataclass(frozen=True, kw_only=True)
# class GenericSnapshot(
#     CanSnapshotAggregate[TAggregateID], GenericDomainEvent[TAggregateID]
# ):
#     """Snapshots represent the state of an aggregate at a particular
#     version.
#
#     Constructor arguments:
#
#     :param TAggregateID originator_id: ID of originating aggregate.
#     :param int originator_version: version of originating aggregate.
#     :param datetime timestamp: date-time of the event
#     :param str topic: string that includes a class and its module
#     :param dict state: state of originating aggregate.
#     """
#
#     topic: str
#     state: dict[str, Any]
#
#
# class Aggregate(BaseAggregate):
#     @staticmethod
#     def create_id(*_: Any, **__: Any) -> UUID:
#         """Returns a new aggregate ID."""
#         return uuid4()
#
#     class Event(AggregateEvent):
#         pass
#
#     class Created(Event, AggregateCreated):
#         pass
#
#     class Snapshot(Snapshot):
#         pass
#
#
# class GenericAggregate(BaseAggregate[TAggregateID]):
#     @classmethod
#     def create_id(cls, *_: Any, **__: Any) -> TAggregateID:
#         """Returns a new aggregate ID."""
#         assert cls.originator_id_type is not None
#         new_id = uuid4()
#         if issubclass(unwrap_new_type(cls.originator_id_type), UUID):
#             return cast(TAggregateID, new_id)
#         if issubclass(unwrap_new_type(cls.originator_id_type), str):
#             return cast(TAggregateID, str(new_id))
#         msg = f"The originator_id_type of {cls} apparently isn't a UUID or str"
#         raise TypeError(msg)
#
#     class Event(GenericAggregateEvent[TAggregateID]):
#         pass
#
#     class Created(GenericAggregateCreated[TAggregateID], Event[TAggregateID]):
#         pass
#
#     class Snapshot(GenericSnapshot[TAggregateID]):
#         pass
#
#
# class AggregateUuidID(GenericAggregate[UUID]):
#     pass
#
#
# class AggregateStrID(GenericAggregate[str]):
#     pass
#
#
# @overload
# def aggregate(*, created_event_name: str) -> Callable[[Any], type[Aggregate]]:
#     pass  # pragma: no cover
#
#
# @overload
# def aggregate(cls: Any) -> type[Aggregate]:
#     pass  # pragma: no cover
#
#
# def aggregate(
#     cls: Any | None = None,
#     *,
#     created_event_name: str = "",
# ) -> type[Aggregate] | Callable[[Any], type[Aggregate]]:
#     """Converts the class that was passed in to inherit from Aggregate.
#
#     .. code-block:: python
#
#         @aggregate
#         class MyAggregate:
#             pass
#
#     ...is equivalent to...
#
#     .. code-block:: python
#
#         class MyAggregate(Aggregate):
#             pass
#     """
#
#     def decorator(cls_: Any) -> type[Aggregate]:
#         if issubclass(cls_, Aggregate):
#             msg = f"{cls_.__qualname__} is already an Aggregate"
#             raise TypeError(msg)
#         bases = cls_.__bases__
#         if bases == (object,):
#             bases = (Aggregate,)
#         else:
#             bases += (Aggregate,)
#         cls_dict = {}
#         cls_dict.update(cls_.__dict__)
#         cls_ = MetaAggregate(
#             cls_.__qualname__,
#             bases,
#             cls_dict,
#             created_event_name=created_event_name,
#         )
#         assert issubclass(cls_, Aggregate)
#         return cls_
#
#     if cls:
#         return decorator(cls)
#     return decorator
