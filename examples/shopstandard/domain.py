from __future__ import annotations

from decimal import Decimal  # noqa: TC003
from typing import override

from eventsourcing.decorator import event
from eventsourcing.pydantic import Aggregate, Decision, Immutable
from examples.shopstandard.exceptions import (
    CartAlreadySubmittedError,
    CartFullError,
    ProductNotInCartError,
)


class ProductDetails(Immutable):
    id: str
    name: str
    description: str
    price: Decimal
    inventory: int


class ProductAdded(Decision):
    product_id: str
    name: str
    description: str
    price: Decimal


class InventoryAdjusted(Decision):
    adjustment: int


class Product(Aggregate):
    @event(ProductAdded)
    def __init__(self, product_id: str, name: str, description: str, price: Decimal):
        self.product_id = product_id
        self.name = name
        self.description = description
        self.price = price
        self.inventory = 0

    @staticmethod
    @override
    def create_id(product_id: str) -> str:
        return product_id

    @event(InventoryAdjusted)
    def adjust_inventory(self, adjustment: int) -> None:
        self.inventory += adjustment


class CartItem(Immutable):
    product_id: str
    name: str
    description: str
    price: Decimal


class CartCreated(Decision):
    cart_id: str


class CartItemAdded(Decision):
    product_id: str
    name: str
    description: str
    price: Decimal


class CartItemRemoved(Decision):
    product_id: str


class CartCleared(Decision):
    pass


class CartSubmitted(Decision):
    pass


class Cart(Aggregate):
    @event(CartCreated)
    def __init__(self, cart_id: str):
        self.cart_id = cart_id
        self.items: list[CartItem] = []
        self.is_submitted = False

    @staticmethod
    @override
    def create_id(cart_id: str) -> str:
        return cart_id

    @event(CartItemAdded)
    def add_item(
        self, product_id: str, name: str, description: str, price: Decimal
    ) -> None:
        if self.is_submitted:
            raise CartAlreadySubmittedError

        if len(self.items) >= 3:
            raise CartFullError

        self.items.append(
            CartItem(
                product_id=product_id,
                name=name,
                description=description,
                price=price,
            )
        )

    @event(CartItemRemoved)
    def remove_item(self, product_id: str) -> None:
        if self.is_submitted:
            raise CartAlreadySubmittedError

        for i, item in enumerate(self.items):
            if item.product_id == product_id:
                self.items.pop(i)
                break
        else:
            raise ProductNotInCartError

    @event(CartCleared)
    def clear(self) -> None:
        if self.is_submitted:
            raise CartAlreadySubmittedError
        self.items = []

    @event(CartSubmitted)
    def submit(self) -> None:
        if self.is_submitted:
            raise CartAlreadySubmittedError
        self.is_submitted = True
