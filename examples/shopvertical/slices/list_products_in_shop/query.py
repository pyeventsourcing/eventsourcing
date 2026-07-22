from __future__ import annotations

from decimal import Decimal  # noqa:TC003
from typing import TYPE_CHECKING

from eventsourcing.pydantic import Immutable
from eventsourcing.utils import get_topic
from examples.shopvertical.common import Query, get_all_events
from examples.shopvertical.events import (
    AddedProductToShop,
    AdjustedProductInventory,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from examples.shopvertical.common import Events


class ProductDetails(Immutable):
    id: str
    name: str
    description: str
    price: Decimal
    inventory: int = 0


class ListProductsInShop(Query):
    @staticmethod
    def projection(events: Events) -> Sequence[ProductDetails]:
        products: dict[str, ProductDetails] = {}
        for event in events:
            match event.decision:
                case AddedProductToShop(
                    name=name, description=description, price=price
                ):
                    products[event.originator_id] = ProductDetails(
                        id=event.originator_id,
                        name=name,
                        description=description,
                        price=price,
                    )
                case AdjustedProductInventory(adjustment=adjustment):
                    product = products[event.originator_id]
                    products[event.originator_id] = ProductDetails(
                        id=event.originator_id,
                        name=product.name,
                        description=product.description,
                        price=product.price,
                        inventory=product.inventory + adjustment,
                    )
        return tuple(products.values())

    def execute(self) -> Sequence[ProductDetails]:
        # TODO: Make this a materialised view.
        return self.projection(
            get_all_events(
                topics=(
                    get_topic(AddedProductToShop),
                    get_topic(AdjustedProductInventory),
                )
            )
        )
