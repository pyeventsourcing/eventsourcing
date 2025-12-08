from decimal import Decimal
from unittest import TestCase
from uuid import UUID, uuid4

from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    DomainEvent,
    RemovedItemFromCart,
)
from examples.shopvertical.slices.get_cart_items.query import GetCartItems


class TestGetCartItems(TestCase):
    def test_cart_empty(self) -> None:
        cart_events: tuple[DomainEvent, ...] = ()
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)

    def test_cart_added_item(self) -> None:
        cart_id: UUID = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="name",
                description="description",
                price=Decimal(1),
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 1)
        self.assertEqual(cart_items[0].product_id, product_id)
        self.assertEqual(cart_items[0].name, "name")
        self.assertEqual(cart_items[0].description, "description")
        self.assertEqual(cart_items[0].price, Decimal(1))

    def test_cart_added_item_and_removed_item(self) -> None:
        cart_id: UUID = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="name",
                description="description",
                price=Decimal(1),
            ),
            RemovedItemFromCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)

    def test_cart_added_two_items_and_removed_two_items(self) -> None:
        cart_id: UUID = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="name",
                description="description",
                price=Decimal(1),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
                name="name",
                description="description",
                price=Decimal(1),
            ),
            RemovedItemFromCart(
                originator_id=cart_id,
                originator_version=3,
                product_id=product_id,
            ),
            RemovedItemFromCart(
                originator_id=cart_id,
                originator_version=4,
                product_id=product_id,
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)

    def test_cart_added_item_and_cleared_cart(self) -> None:
        cart_id: UUID = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="name",
                description="description",
                price=Decimal(1),
            ),
            ClearedCart(
                originator_id=cart_id,
                originator_version=2,
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)
