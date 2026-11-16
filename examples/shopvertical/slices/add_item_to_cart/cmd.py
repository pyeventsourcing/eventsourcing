from __future__ import annotations

from decimal import Decimal  # noqa: TC003
from typing import TYPE_CHECKING, override

from eventsourcing.domain import StreamEvent
from examples.shopvertical.common import Command, get_events, put_events
from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    RemovedItemFromCart,
    SubmittedCart,
)
from examples.shopvertical.exceptions import CartAlreadySubmittedError, CartFullError

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class AddItemToCart(Command):
    cart_id: str
    product_id: str
    description: str
    price: Decimal
    name: str

    @override
    def handle(self, events: Events) -> Events:
        product_ids = []
        is_submitted = False
        for event in events:
            match event.decision:
                case AddedItemToCart(product_id=product_id):
                    product_ids.append(product_id)
                case RemovedItemFromCart(product_id=product_id):
                    product_ids.remove(product_id)
                case ClearedCart():
                    product_ids.clear()
                case SubmittedCart():
                    is_submitted = True

        if is_submitted:
            raise CartAlreadySubmittedError

        if len(product_ids) >= 3:
            raise CartFullError

        return (
            StreamEvent(
                decision=AddedItemToCart(
                    product_id=self.product_id,
                    name=self.name,
                    description=self.description,
                    price=self.price,
                ),
                stream_id=self.cart_id,
                stream_position=len(events) + 1,
            ),
        )

    @override
    def execute(self) -> int | None:
        return put_events(self.handle(get_events(self.cart_id)))
