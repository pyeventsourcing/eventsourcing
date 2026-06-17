import unittest
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from examples.shopvertical.events import ClearedCart, SubmittedCart
from examples.shopvertical.exceptions import CartAlreadySubmittedError
from examples.shopvertical.slices.clear_cart.cmd import (
    ClearCart,
)

if TYPE_CHECKING:
    from examples.aggregate7.immutablemodel import DomainEvent


class TestClearCart(unittest.TestCase):
    def test_clear_cart(self) -> None:
        cart_id = uuid4()
        cmd = ClearCart(
            cart_id=cart_id,
        )
        events: tuple[DomainEvent, ...] = ()
        new_events = cmd.handle(events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], ClearedCart)
        new_event = cast(ClearedCart, new_events[0])
        self.assertEqual(new_event.originator_id, cart_id)
        self.assertEqual(new_event.originator_version, 1)

    def test_clear_cart_after_submitted_cart(self) -> None:
        cart_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            SubmittedCart(
                originator_id=cart_id,
                originator_version=1,
            ),
        )

        cmd = ClearCart(
            cart_id=cart_id,
        )

        with self.assertRaises(CartAlreadySubmittedError):
            cmd.handle(cart_events)
