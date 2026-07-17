import unittest
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from eventsourcing.domain_new import AggregateEvent
from examples.shopvertical.events import (
    AddedItemToCart,
    AddedProductToShop,
    AdjustedProductInventory,
)
from examples.shopvertical.slices.list_products_in_shop.query import ListProductsInShop

if TYPE_CHECKING:
    from eventsourcing.pydantic.immutable import DomainEvent


class TestListProductsInShop(unittest.TestCase):
    def test_list_products_one_product(self) -> None:
        products = ListProductsInShop.projection(())
        self.assertEqual(len(products), 0)

        product_id1 = str(uuid4())
        events: Events = (
            AggregateEvent(
                decision=AddedProductToShop(
                    name="Coffee",
                    description="A very nice coffee",
                    price=Decimal("5.99"),
                ),
                originator_id=product_id1,
                originator_version=1,
            ),
        )
        products = ListProductsInShop.projection(events)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].id, product_id1)
        self.assertEqual(products[0].name, "Coffee")
        self.assertEqual(products[0].description, "A very nice coffee")
        self.assertEqual(products[0].price, Decimal("5.99"))
        self.assertEqual(products[0].inventory, 0)

    def test_list_products_two_products_also_item_added_to_cart(self) -> None:

        product_id1 = str(uuid4())
        product_id2 = str(uuid4())
        events = (
            AggregateEvent(
                decision=AddedProductToShop(
                    name="Coffee",
                    description="A very nice coffee",
                    price=Decimal("5.99"),
                ),
                originator_id=product_id1,
                originator_version=1,
            ),
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=str(uuid4()),
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=uuid4(),
                originator_version=1,
            ),
            AggregateEvent(
                decision=AddedProductToShop(
                    name="Tea",
                    description="A very nice tea",
                    price=Decimal("3.99"),
                ),
                originator_id=product_id2,
                originator_version=1,
            ),
        )
        products = ListProductsInShop.projection(events)
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0].id, product_id1)
        self.assertEqual(products[0].name, "Coffee")
        self.assertEqual(products[0].description, "A very nice coffee")
        self.assertEqual(products[0].price, Decimal("5.99"))
        self.assertEqual(products[0].inventory, 0)
        self.assertEqual(products[1].id, product_id2)
        self.assertEqual(products[1].name, "Tea")
        self.assertEqual(products[1].description, "A very nice tea")
        self.assertEqual(products[1].price, Decimal("3.99"))
        self.assertEqual(products[1].inventory, 0)

    def test_list_products_two_products_also_adjusted_inventory(self) -> None:

        product_id1 = str(uuid4())
        product_id2 = str(uuid4())
        events = (
            AggregateEvent(
                decision=AddedProductToShop(
                    name="Coffee",
                    description="A very nice coffee",
                    price=Decimal("5.99"),
                ),
                originator_id=product_id1,
                originator_version=1,
            ),
            AggregateEvent(
                decision=AdjustedProductInventory(
                    adjustment=2,
                ),
                originator_id=product_id1,
                originator_version=2,
            ),
            AggregateEvent(
                decision=AddedProductToShop(
                    name="Tea",
                    description="A very nice tea",
                    price=Decimal("3.99"),
                ),
                originator_id=product_id2,
                originator_version=1,
            ),
        )
        products = ListProductsInShop.projection(events)
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0].id, product_id1)
        self.assertEqual(products[0].name, "Coffee")
        self.assertEqual(products[0].description, "A very nice coffee")
        self.assertEqual(products[0].price, Decimal("5.99"))
        self.assertEqual(products[0].inventory, 2)
        self.assertEqual(products[1].id, product_id2)
        self.assertEqual(products[1].name, "Tea")
        self.assertEqual(products[1].description, "A very nice tea")
        self.assertEqual(products[1].price, Decimal("3.99"))
        self.assertEqual(products[1].inventory, 0)
