from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from eventsourcing.pydantic.immutablemodel import Immutable
from eventsourcing.utils import get_topic
from examples.shopvertical.common import Query, get_all_events
from examples.shopvertical.events import (
    AddedProductToShop,
    AdjustedProductInventory,
    DomainEvents,
)


class ProductDetails(Immutable):
    id: UUID
    name: str
    description: str
    price: Decimal
    inventory: int = 0


class ListProductsInShop(Query):
    @staticmethod
    def projection(events: DomainEvents) -> Sequence[ProductDetails]:
        products: dict[UUID, ProductDetails] = {}
        for event in events:
            if isinstance(event, AddedProductToShop):
                products[event.originator_id] = ProductDetails(
                    id=event.originator_id,
                    name=event.name,
                    description=event.description,
                    price=event.price,
                )
            elif isinstance(event, AdjustedProductInventory):
                product = products[event.originator_id]
                products[event.originator_id] = ProductDetails(
                    id=event.originator_id,
                    name=product.name,
                    description=product.description,
                    price=product.price,
                    inventory=product.inventory + event.adjustment,
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
