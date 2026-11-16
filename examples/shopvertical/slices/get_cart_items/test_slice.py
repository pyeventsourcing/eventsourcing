from decimal import Decimal
from typing import TYPE_CHECKING
from unittest import TestCase
from uuid import uuid4

from eventsourcing.domain import StreamEvent
from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    RemovedItemFromCart,
)
from examples.shopvertical.slices.get_cart_items.query import GetCartItems

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class TestGetCartItems(TestCase):
    def test_cart_empty(self) -> None:
        cart_events: Events = ()
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)

    def test_cart_added_item(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            StreamEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="name",
                    description="description",
                    price=Decimal(1),
                ),
                stream_id=cart_id,
                stream_position=1,
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 1)
        self.assertEqual(cart_items[0].product_id, product_id)
        self.assertEqual(cart_items[0].name, "name")
        self.assertEqual(cart_items[0].description, "description")
        self.assertEqual(cart_items[0].price, Decimal(1))

    def test_cart_added_item_and_removed_item(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            StreamEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="name",
                    description="description",
                    price=Decimal(1),
                ),
                stream_id=cart_id,
                stream_position=1,
            ),
            StreamEvent(
                decision=RemovedItemFromCart(
                    product_id=product_id,
                ),
                stream_id=cart_id,
                stream_position=2,
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)

    def test_cart_added_two_items_and_removed_two_items(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            StreamEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="name",
                    description="description",
                    price=Decimal(1),
                ),
                stream_id=cart_id,
                stream_position=1,
            ),
            StreamEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="name",
                    description="description",
                    price=Decimal(1),
                ),
                stream_id=cart_id,
                stream_position=2,
            ),
            StreamEvent(
                decision=RemovedItemFromCart(
                    product_id=product_id,
                ),
                stream_id=cart_id,
                stream_position=3,
            ),
            StreamEvent(
                decision=RemovedItemFromCart(
                    product_id=product_id,
                ),
                stream_id=cart_id,
                stream_position=4,
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)

    def test_cart_added_item_and_cleared_cart(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            StreamEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="name",
                    description="description",
                    price=Decimal(1),
                ),
                stream_id=cart_id,
                stream_position=1,
            ),
            StreamEvent(
                decision=ClearedCart(),
                stream_id=cart_id,
                stream_position=2,
            ),
        )
        cart_items = GetCartItems.projection(cart_events)
        self.assertEqual(len(cart_items), 0)
