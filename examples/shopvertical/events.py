from __future__ import annotations

from decimal import Decimal  # noqa: TC003

from eventsourcing.pydantic.immutable import PydanticDecision


class AddedProductToShop(PydanticDecision):
    name: str
    description: str
    price: Decimal


class AdjustedProductInventory(PydanticDecision):
    adjustment: int


class AddedItemToCart(PydanticDecision):
    product_id: str
    name: str
    description: str
    price: Decimal


class RemovedItemFromCart(PydanticDecision):
    product_id: str


class ClearedCart(PydanticDecision):
    pass


class SubmittedCart(PydanticDecision):
    pass
