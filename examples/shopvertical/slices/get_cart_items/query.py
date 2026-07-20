from __future__ import annotations

from decimal import Decimal  # noqa:TC003
from typing import TYPE_CHECKING

from eventsourcing.pydantic.immutable import Immutable
from examples.shopvertical.common import Query, get_events
from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    RemovedItemFromCart,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from examples.shopvertical.common import Events


class CartItem(Immutable):
    product_id: str
    name: str
    description: str
    price: Decimal


class GetCartItems(Query):
    cart_id: str

    @staticmethod
    def projection(events: Events) -> Sequence[CartItem]:
        cart_items: list[CartItem] = []
        for event in events:
            match event.decision:
                case AddedItemToCart(
                    product_id=product_id,
                    name=name,
                    description=description,
                    price=price,
                ):
                    cart_items.append(
                        CartItem(
                            product_id=product_id,
                            name=name,
                            description=description,
                            price=price,
                        )
                    )
                case RemovedItemFromCart(product_id=product_id):
                    for i, cart_item in enumerate(cart_items):
                        if cart_item.product_id == product_id:
                            cart_items.pop(i)
                            break
                case ClearedCart():
                    cart_items.clear()
        return tuple(cart_items)

    def execute(self) -> Sequence[CartItem]:
        return self.projection(get_events(self.cart_id))
