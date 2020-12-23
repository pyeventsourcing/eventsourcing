from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar
from uuid import UUID


class FrozenDataClass(type):
    def __new__(cls, *args):
        new_cls = super().__new__(cls, *args)
        return dataclass(frozen=True)(new_cls)


class ImmutableObject(metaclass=FrozenDataClass):
    pass


class DomainEvent(ImmutableObject):
    originator_id: UUID
    originator_version: int
    timestamp: datetime


TDomainEvent = TypeVar("TDomainEvent", bound=DomainEvent)
