import unittest
from decimal import Decimal
from typing import cast
from uuid import uuid4

from examples.shopvertical.common import reset_application
from examples.shopvertical.events import (
    AddedItemToCart,
    ClearedCart,
    DomainEvent,
    RemovedItemFromCart,
    SubmittedCart,
)
from examples.shopvertical.exceptions import (
    CartAlreadySubmittedError,
    InsufficientInventoryError,
)
from examples.shopvertical.slices.add_product_to_shop.cmd import AddProductToShop
from examples.shopvertical.slices.adjust_product_inventory.cmd import (
    AdjustProductInventory,
)
from examples.shopvertical.slices.submit_cart.cmd import (
    SubmitCart,
)


class TestSubmitCart(unittest.TestCase):
    def setUp(self) -> None:
        reset_application()

    def test_submit_cart_sufficient_inventory_empty_cart(self) -> None:
        cart_id = uuid4()
        cmd = SubmitCart(
            cart_id=cart_id,
        )
        cart_events: tuple[DomainEvent, ...] = ()
        new_events = cmd.handle(cart_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], SubmittedCart)
        new_event = cast(SubmittedCart, new_events[0])
        self.assertEqual(new_event.originator_id, cart_id)
        self.assertEqual(new_event.originator_version, 1)

    def test_submit_cart_sufficient_inventory_after_item_removed(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()
        cmd = SubmitCart(
            cart_id=cart_id,
        )
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
        new_events = cmd.handle(cart_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], SubmittedCart)
        new_event = cast(SubmittedCart, new_events[0])
        self.assertEqual(new_event.originator_id, cart_id)
        self.assertEqual(new_event.originator_version, 3)

    def test_submit_cart_sufficient_inventory_after_cart_cleared(self) -> None:
        cart_id = uuid4()
        cmd = SubmitCart(
            cart_id=cart_id,
        )
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=uuid4(),
                name="",
                description="",
                price=Decimal(1),
            ),
            ClearedCart(
                originator_id=cart_id,
                originator_version=2,
            ),
        )
        new_events = cmd.handle(cart_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], SubmittedCart)
        new_event = cast(SubmittedCart, new_events[0])
        self.assertEqual(new_event.originator_id, cart_id)
        self.assertEqual(new_event.originator_version, 3)

    def test_submit_cart_insufficient_inventory_after_item_added(self) -> None:
        cart_id = uuid4()
        cmd = SubmitCart(
            cart_id=cart_id,
        )
        product_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(100),
            ),
        )
        with self.assertRaises(InsufficientInventoryError):
            cmd.handle(cart_events)

    def test_submit_cart_sufficient_inventory_after_item_added(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()

        AddProductToShop(
            product_id=product_id,
            name="",
            description="",
            price=Decimal(100),
        ).execute()
        AdjustProductInventory(
            product_id=product_id,
            adjustment=1,
        ).execute()

        cmd = SubmitCart(
            cart_id=cart_id,
        )
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(100),
            ),
        )
        new_events = cmd.handle(cart_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], SubmittedCart)
        new_event = cast(SubmittedCart, new_events[0])
        self.assertEqual(new_event.originator_id, cart_id)
        self.assertEqual(new_event.originator_version, 2)

    def test_submit_cart_insufficient_inventory_after_item_added_twice(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()

        AddProductToShop(
            product_id=product_id,
            name="",
            description="",
            price=Decimal(100),
        ).execute()
        AdjustProductInventory(
            product_id=product_id,
            adjustment=1,
        ).execute()

        cmd = SubmitCart(cart_id=cart_id)

        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(100),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(100),
            ),
        )
        with self.assertRaises(InsufficientInventoryError):
            cmd.handle(cart_events)

    def test_submit_cart_sufficient_inventory_after_item_added_twice(self) -> None:
        cart_id = uuid4()
        product_id = uuid4()

        AddProductToShop(
            product_id=product_id,
            name="",
            description="",
            price=Decimal(100),
        ).execute()
        AdjustProductInventory(
            product_id=product_id,
            adjustment=2,
        ).execute()

        cmd = SubmitCart(
            cart_id=cart_id,
        )
        cart_events: tuple[DomainEvent, ...] = (
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=1,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(100),
            ),
            AddedItemToCart(
                originator_id=cart_id,
                originator_version=2,
                product_id=product_id,
                name="",
                description="",
                price=Decimal(100),
            ),
        )
        new_events = cmd.handle(cart_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0], SubmittedCart)
        new_event = cast(SubmittedCart, new_events[0])
        self.assertEqual(new_event.originator_id, cart_id)
        self.assertEqual(new_event.originator_version, 3)

    def test_submit_cart_after_submitted_cart(self) -> None:
        cart_id = uuid4()
        cart_events: tuple[DomainEvent, ...] = (
            SubmittedCart(
                originator_id=cart_id,
                originator_version=1,
            ),
        )

        cmd = SubmitCart(
            cart_id=cart_id,
        )

        with self.assertRaises(CartAlreadySubmittedError):
            cmd.handle(cart_events)
