import unittest
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import uuid4

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
    from examples.aggregate7.immutablemodel import DomainEvent


class TestAddItemToCart(unittest.TestCase):
    def test_add_item_to_empty_cart(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=product_id,
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )
        cart_events: tuple[DomainEvent, ...] = ()
        new_events = cmd.handle(cart_events)
        self.assertEqual(1, len(new_events))
        self.assertIsInstance(new_events[0], AddedItemToCart)
        new_event = cast(AddedItemToCart, new_events[0])
        self.assertEqual(cmd.product_id, new_event.product_id)

    def test_add_item_to_full_cart(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=3,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=uuid4(),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        with self.assertRaises(CartFullError):
            cmd.handle(cart_events)

    def test_add_item_to_cart_after_adding_three_and_removing_one(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=3,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            RemovedItemFromCart(
                originator_id=cart_id,
                originator_version=4,
                product_id=product_id,
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=uuid4(),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        cmd.handle(cart_events)

    def test_add_item_to_cart_after_adding_three_and_clearing_cart(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=3,
                product_id=product_id,
                name="",
                description="",
                price=Decimal("5.99"),
            ),
            ClearedCart(
                originator_id=cart_id,
                originator_version=4,
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=uuid4(),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        cmd.handle(cart_events)

    def test_add_item_after_submitted_cart(self) -> None:
        cart_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            SubmittedCart(
                originator_id=cart_id,
                originator_version=1,
            ),
        )

        cmd = AddItemToCart(
            cart_id=cart_id,
            product_id=uuid4(),
            name="Coffee",
            description="A very special coffee",
            price=Decimal("5.99"),
        )

        with self.assertRaises(CartAlreadySubmittedError):
            cmd.handle(cart_events)
