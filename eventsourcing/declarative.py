# import inspect
# from builtins import property
# from copy import copy
# from dataclasses import dataclass
# from datetime import datetime
# from types import FunctionType
# from typing import Any, Callable, Dict, Iterable, Optional, Type, Union, cast
# from uuid import UUID
#
# from eventsourcing.domain import (
#     Aggregate,
#     Aggregate,
#     MetaAggregate,
#     TAggregate,
# )
#
#
# class MetaDecoratableAggregate(MetaAggregate):
#     def __new__(
#         cls, cls_name: str, bases: tuple, cls_dict: Dict[str, Any]
#     ) -> "MetaDecoratableAggregate":
#         if cls_name == "DecoratableAggregate":
#             aggregate_class = MetaAggregate.__new__(cls, cls_name, bases, cls_dict)
#             return cast(MetaDecoratableAggregate, aggregate_class)
#         else:
#             cls_dict["_original_init_method"] = cls_dict.pop("__init__", None)
#             bases = bases + (DecoratedAggregate,)
#             aggregate_class = super().__new__(cls, cls_name, bases, cls_dict)
#             return cast(MetaDecoratableAggregate, aggregate_class)
#
#     def __init__(self, cls_name: str, bases: tuple, cls_dict: Dict[str, Any]):
#         super().__init__(cls_name, bases, cls_dict)
#         if cls_name == "DecoratableAggregate":
#             return
#
#         original_init_method = cls_dict["_original_init_method"]
#
#         # Prepare the "created" event class.
#         for cls_attr in tuple(cls_dict.values()):
#             if isinstance(cls_attr, type) and issubclass(
#                 cls_attr, Aggregate.Created
#             ):
#                 # Found a "created" class on the aggregate.
#                 self._created_cls = cls_attr
#                 break
#         else:
#             created_cls_annotations = {}
#             if original_init_method:
#                 _check_no_variable_params(original_init_method)
#                 method_signature = inspect.signature(original_init_method)
#                 for param_name in method_signature.parameters:
#                     if param_name == "self":
#                         continue
#                     created_cls_annotations[param_name] = "typing.Any"
#
#             created_cls_name = "Created"
#             created_cls_dict = {
#                 "__annotations__": created_cls_annotations,
#                 "__qualname__": ".".join([self.__qualname__, created_cls_name]),
#                 "__module__": self.__qualname__,
#             }
#
#             # Define the created class.
#             created_cls = type(
#                 created_cls_name, (Aggregate.Created,), created_cls_dict
#             )
#             # Put it in the aggregate class dict.
#             cls_dict[created_cls_name] = created_cls
#             self._created_cls = created_cls
#
#         # Prepare the __init__ method.
#         self._original_init_method = original_init_method
#
#         # Prepare the subsequent event classes.
#         for attribute in tuple(cls_dict.values()):
#
#             # Watch out for @property that sits over an @event.
#             if isinstance(attribute, property) and isinstance(
#                 attribute.fset, EventDecorator
#             ):
#                 attribute = attribute.fset
#                 if attribute.is_name_inferred_from_method:
#                     # We don't want name inferred from property (not past participle).
#                     method_name = attribute.original_method.__name__
#                     raise TypeError(
#                         f"@event under {method_name}() property setter requires event "
#                         f"class name"
#                     )
#                 # Attribute is a property decorating an event decorator.
#                 attribute.is_property_setter = True
#
#             # Attribute is an event decorator.
#             if isinstance(attribute, EventDecorator):
#                 # Prepare the subsequent aggregate events.
#                 original_method = attribute.original_method
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
#                     annotations[param_name] = "typing.Any"  # Todo: Improve this?
#
#                 if not attribute.given_event_cls:
#                     event_cls_name = attribute.event_cls_name
#
#                     # Check event class isn't already defined.
#                     if event_cls_name in cls_dict:
#                         raise TypeError(
#                             f"{event_cls_name} event already defined on {cls_name}"
#                         )
#
#                     event_cls_qualname = ".".join([self.__qualname__, event_cls_name])
#                     event_cls_dict = {
#                         "__annotations__": annotations,
#                         "__module__": self.__module__,
#                         "__qualname__": event_cls_qualname,
#                     }
#                     event_cls = type(event_cls_name, (DecoratedEvent,), event_cls_dict)
#                     original_methods[event_cls] = original_method
#                     cls_dict[event_cls_name] = event_cls
#                     setattr(self, event_cls_name, event_cls)
#
#     def __call__(self, *args: Any, **kwargs: Any) -> TAggregate:
#         if self._original_init_method is not None:
#             kwargs = _coerce_args_to_kwargs(self._original_init_method, args, kwargs)
#         else:
#             if args or kwargs:
#                 raise TypeError(f"{self.__name__}() takes no args")
#         aggregate: TAggregate = self._create(
#             event_class=self._created_cls,
#             **kwargs,
#         )
#         return aggregate
#
#
#
#
#
# class DecoratableAggregate(metaclass=MetaDecoratableAggregate):
#     id: UUID
#     version: int
#     created_on: datetime
#     modified_on: datetime
#
#
# class DecoratedAggregate(Aggregate):
#     _original_init_method: Optional[FunctionType] = None
#
#     def __new__(cls, *args: Any, **kwargs: Any) -> Any:
#         return super(DecoratedAggregate, cls).__new__(cls, *args, **kwargs)
#
#     def __init__(self, **kwargs: Any) -> None:
#         base_kwargs = {}
#         base_kwargs["id"] = kwargs.pop("id")
#         base_kwargs["version"] = kwargs.pop("version")
#         base_kwargs["timestamp"] = kwargs.pop("timestamp")
#         super().__init__(**base_kwargs)
#         if self._original_init_method:
#             self._original_init_method(**kwargs)
#
#     def __getattribute__(self, item: str) -> Any:
#         attr = super().__getattribute__(item)
#         if isinstance(attr, EventDecorator):
#             if attr.is_decorating_a_property:
#                 assert attr.decorated_property
#                 assert attr.decorated_property.fget
#                 return attr.decorated_property.fget(self)  # type: ignore
#             else:
#                 return BoundEvent(attr, self)
#         else:
#             return attr
#
#     def __setattr__(self, name: str, value: Any) -> Any:
#         try:
#             attr = super().__getattribute__(name)
#         except AttributeError:
#             # Set new attribute.
#             super().__setattr__(name, value)
#         else:
#             if isinstance(attr, EventDecorator):
#                 # Set decorated property.
#                 b = BoundEvent(attr, self)
#                 kwargs = {name: value}
#                 b.trigger(**kwargs)
#
#             else:
#                 # Set existing attribute.
#                 super().__setattr__(name, value)
#
#
# def aggregate(
#     cls: Any = None, *, is_dataclass: Optional[bool] = None
# ) -> Union[MetaDecoratableAggregate, Callable[[Any], MetaDecoratableAggregate]]:
#     """Returns the same class as was passed in, with dunder methods
#     added based on the fields defined in the class.
#
#     :rtype: Union[MetaDecoratableAggregate, Callable[[Any], MetaDecoratableAggregate]]
#     """
#
#     def wrapper(cls: Any) -> MetaDecoratableAggregate:
#         if is_dataclass:
#             cls = dataclass(cls)
#         cls_dict = {k: v for k, v in cls.__dict__.items()}
#         cls_dict["__qualname__"] = cls.__qualname__
#         return MetaDecoratableAggregate(cls.__name__, (), cls_dict)
#
#     if cls:
#         assert is_dataclass is None
#         return wrapper(cls)
#     else:
#         return wrapper
