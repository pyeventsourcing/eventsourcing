from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from eventsourcing.domain import AggregateEvent
from examples.shopvertical.common import Command, get_events, put_events
from examples.shopvertical.events import (
    AddedItemToCart,
    AdjustedProductInventory,
    ClearedCart,
    RemovedItemFromCart,
    SubmittedCart,
)
from examples.shopvertical.exceptions import (
    CartAlreadySubmittedError,
    InsufficientInventoryError,
)

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class SubmitCart(Command):
    cart_id: str

    def handle(self, events: Events) -> Events:
        requested_products: dict[str, int] = defaultdict(int)
        is_submitted = False

        for event in events:
            match event.decision:
                case AddedItemToCart(product_id=product_id):
                    requested_products[product_id] += 1
                case RemovedItemFromCart(product_id=product_id):
                    requested_products[product_id] -= 1
                case ClearedCart():
                    requested_products.clear()
                case SubmittedCart():
                    is_submitted = True

        if is_submitted:
            raise CartAlreadySubmittedError

        # Check inventory.
        for product_id, requested_amount in requested_products.items():
            current_inventory = 0
            for product_event in get_events(product_id):
                match product_event.decision:
                    case AdjustedProductInventory(adjustment=adjustment):
                        current_inventory += adjustment
            if current_inventory < requested_amount:
                msg = f"Insufficient inventory for product with ID {product_id}"
                raise InsufficientInventoryError(msg)

        return (
            AggregateEvent(
                decision=SubmittedCart(),
                originator_id=self.cart_id,
                originator_version=len(events) + 1,
            ),
        )

    def execute(self) -> int | None:
        return put_events(self.handle(get_events(self.cart_id)))
