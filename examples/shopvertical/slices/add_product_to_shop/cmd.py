from __future__ import annotations

from decimal import Decimal  # noqa: TC003
from typing import TYPE_CHECKING

from eventsourcing.domain_new import AggregateEvent
from examples.shopvertical.common import Command, get_events, put_events
from examples.shopvertical.events import AddedProductToShop
from examples.shopvertical.exceptions import ProductAlreadyInShopError

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class AddProductToShop(Command):
    product_id: str
    name: str
    description: str
    price: Decimal

    def handle(self, events: Events) -> Events:
        if len(events):
            raise ProductAlreadyInShopError
        return (
            AggregateEvent(
                decision=AddedProductToShop(
                    name=self.name,
                    description=self.description,
                    price=self.price,
                ),
                originator_id=self.product_id,
                originator_version=1,
            ),
        )

    def execute(self) -> int | None:
        return put_events(self.handle(get_events(self.product_id)))
