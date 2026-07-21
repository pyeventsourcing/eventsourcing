from __future__ import annotations

from decimal import Decimal  # noqa: TC003

from eventsourcing.pydantic import Decision


class AddedProductToShop(Decision):
    name: str
    description: str
    price: Decimal


class AdjustedProductInventory(Decision):
    adjustment: int


class AddedItemToCart(Decision):
    product_id: str
    name: str
    description: str
    price: Decimal


class RemovedItemFromCart(Decision):
    product_id: str


class ClearedCart(Decision):
    pass


class SubmittedCart(Decision):
    pass
