from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal  # noqa: TC003
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from examples.aggregate7.immutablemodel import Immutable

if TYPE_CHECKING:
    from typing import TypeAlias


class DomainEvent(Immutable):
    originator_id: UUID
    originator_version: int


DomainEvents: TypeAlias = Sequence[DomainEvent]


class AddedProductToShop(DomainEvent):
    name: str
    description: str
    price: Decimal


class AdjustedProductInventory(DomainEvent):
    adjustment: int


class AddedItemToCart(DomainEvent):
    product_id: UUID
    name: str
    description: str
    price: Decimal


class RemovedItemFromCart(DomainEvent):
    product_id: UUID


class ClearedCart(DomainEvent):
    pass


class SubmittedCart(DomainEvent):
    pass
