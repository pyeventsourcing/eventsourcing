import unittest
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from eventsourcing.domain import AggregateEvent
from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    RemovedItemFromCart,
    SubmittedCart,
)
from examples.shopvertical.exceptions import CartAlreadySubmittedError, CartFullError
from examples.shopvertical.slices.add_item_to_cart.cmd import (
    AddItemToCart,
)

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class TestAddItemToCart(unittest.TestCase):
    def test_add_item_to_empty_cart(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=product_id,
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )
        cart_events: Events = ()
        new_events = cmd.handle(cart_events)
        self.assertEqual(1, len(new_events))
        self.assertIsInstance(new_events[0].decision, AddedItemToCart)
        new_event = cast(AddedItemToCart, new_events[0].decision)
        self.assertEqual(cmd.product_id, new_event.product_id)

    def test_add_item_to_full_cart(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=1,
            ),
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=2,
            ),
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=3,
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=str(uuid4()),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        with self.assertRaises(CartFullError):
            cmd.handle(cart_events)

    def test_add_item_to_cart_after_adding_three_and_removing_one(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=1,
            ),
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=2,
            ),
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=3,
            ),
            AggregateEvent(
                decision=RemovedItemFromCart(
                    product_id=product_id,
                ),
                originator_id=cart_id,
                originator_version=4,
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=str(uuid4()),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        cmd.handle(cart_events)

    def test_add_item_to_cart_after_adding_three_and_clearing_cart(self) -> None:
        cart_id = str(uuid4())
        product_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=1,
            ),
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=2,
            ),
            AggregateEvent(
                decision=AddedItemToCart(
                    product_id=product_id,
                    name="",
                    description="",
                    price=Decimal("5.99"),
                ),
                originator_id=cart_id,
                originator_version=3,
            ),
            AggregateEvent(
                decision=ClearedCart(),
                originator_id=cart_id,
                originator_version=4,
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=str(uuid4()),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        cmd.handle(cart_events)

    def test_add_item_after_submitted_cart(self) -> None:
        cart_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=SubmittedCart(),
                originator_id=cart_id,
                originator_version=1,
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=str(uuid4()),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        with self.assertRaises(CartAlreadySubmittedError):
            cmd.handle(cart_events)
