from __future__ import annotations

import unittest
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from eventsourcing.domain_new import AggregateEvent
from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    RemovedItemFromCart,
    SubmittedCart,
)
from examples.shopvertical.exceptions import (
    CartAlreadySubmittedError,
    ProductNotInCartError,
)
from examples.shopvertical.slices.remove_item_from_cart.cmd import (
    RemoveItemFromCart,
)

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class TestRemoveItemFromCart(unittest.TestCase):
    def test_remove_item_from_empty_cart(self) -> None:
        cart_events = ()
        cmd = RemoveItemFromCart(
            cart_id=str(uuid4()),
            product_id=str(uuid4()),
        )
        with self.assertRaises(ProductNotInCartError):
            cmd.handle(cart_events)

    def test_remove_item_from_cart_after_item_added(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal(1),
                ),
                originator_id=cart_id,
                originator_version=1,
            ),
        )
        cmd = RemoveItemFromCart(
            cart_id=cart_id,
            product_id=product_id,
        )
        new_events = cmd.handle(cart_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0].decision, RemovedItemFromCart)

    def test_remove_item_from_cart_after_item_removed(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal(1),
                ),
                originator_id=cart_id,
                originator_version=1,
            ),
            AggregateEvent(
                decision=RemovedItemFromCart(
                    product_id=product_id,
                ),
                originator_id=cart_id,
                originator_version=2,
            ),
        )
        cmd = RemoveItemFromCart(
            cart_id=cart_id,
            product_id=product_id,
        )
        with self.assertRaises(ProductNotInCartError):
            cmd.handle(cart_events)

    def test_remove_item_from_cart_after_cart_cleared(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal(1),
                ),
                originator_id=cart_id,
                originator_version=1,
            ),
            AggregateEvent(
                decision=ClearedCart(),
                originator_id=cart_id,
                originator_version=2,
            ),
        )
        cmd = RemoveItemFromCart(
            cart_id=cart_id,
            product_id=product_id,
        )
        with self.assertRaises(ProductNotInCartError):
            cmd.handle(cart_events)

    def test_remove_item_from_cart_after_submitted_cart(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=SubmittedCart(),
                originator_id=cart_id,
                originator_version=1,
            ),
        )
        cmd = RemoveItemFromCart(
            cart_id=cart_id,
            product_id=product_id,
        )
        with self.assertRaises(CartAlreadySubmittedError):
            cmd.handle(cart_events)

        with self.assertRaises(CartAlreadySubmittedError):
            cmd.handle(cart_events)
