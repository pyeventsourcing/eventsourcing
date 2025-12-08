import unittest
from decimal import Decimal
from uuid import uuid4

from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    DomainEvent,
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


class TestRemoveItemFromCart(unittest.TestCase):
    def test_remove_item_from_empty_cart(self) -> None:
        cart_events = ()
        cmd = RemoveItemFromCart(
            cart_id=uuid4(),
            product_id=uuid4(),
        )
        with self.assertRaises(ProductNotInCartError):
            cmd.handle(cart_events)

    def test_remove_item_from_cart_after_item_added(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(1),
            ),
        )
        cmd = RemoveItemFromCart(
            cart_id=cart_id,
            product_id=product_id,
        )
        new_events = cmd.handle(cart_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], RemovedItemFromCart)

    def test_remove_item_from_cart_after_item_removed(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(1),
            ),
            RemovedItemFromCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
            ),
        )
        cmd = RemoveItemFromCart(
            cart_id=cart_id,
            product_id=product_id,
        )
        with self.assertRaises(ProductNotInCartError):
            cmd.handle(cart_events)

    def test_remove_item_from_cart_after_cart_cleared(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(1),
            ),
            ClearedCart(
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
        cart_id = uuid4()
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            SubmittedCart(
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
