import unittest
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from eventsourcing.domain import AggregateEvent
from examples.shopvertical.events import ClearedCart, SubmittedCart
from examples.shopvertical.exceptions import CartAlreadySubmittedError
from examples.shopvertical.slices.clear_cart.cmd import (
    ClearCart,
)

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class TestClearCart(unittest.TestCase):
    def test_clear_cart(self) -> None:
        cart_id = str(uuid4())
        cmd = ClearCart(
            cart_id=cart_id,
        )
        events: Events = ()
        new_events = cmd.handle(events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0].decision, ClearedCart)
        new_event = cast(AggregateEvent[ClearedCart], new_events[0])
        self.assertEqual(new_event.originator_id, cart_id)
        self.assertEqual(new_event.originator_version, 1)

    def test_clear_cart_after_submitted_cart(self) -> None:
        cart_id = str(uuid4())
        cart_events: Events = (
            AggregateEvent(
                decision=SubmittedCart(),
                originator_id=cart_id,
                originator_version=1,
            ),
        )

        cmd = ClearCart(
            cart_id=cart_id,
        )

        with self.assertRaises(CartAlreadySubmittedError):
            cmd.handle(cart_events)
