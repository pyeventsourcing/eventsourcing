from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from eventsourcing.pydantic.immutablemodel import Immutable
from examples.shopvertical.common import Query, get_events
from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    DomainEvents,
    RemovedItemFromCart,
)


class CartItem(Immutable):
    product_id: UUID
    name: str
    description: str
    price: Decimal


class GetCartItems(Query):
    cart_id: UUID

    @staticmethod
    def projection(events: DomainEvents) -> Sequence[CartItem]:
        cart_items: list[CartItem] = []
        for event in events:
            if isinstance(event, AddedItemToCart):
                cart_items.append(
                    CartItem(
                        product_id=event.product_id,
                        name=event.name,
                        description=event.description,
                        price=event.price,
                    )
                )
            elif isinstance(event, RemovedItemFromCart):
                for i, cart_item in enumerate(cart_items):
                    if cart_item.product_id == event.product_id:
                        cart_items.pop(i)
                        break
            elif isinstance(event, ClearedCart):
                cart_items.clear()
        return tuple(cart_items)

    def execute(self) -> Sequence[CartItem]:
        return self.projection(get_events(self.cart_id))
