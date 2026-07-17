from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, cast
from unittest import TestCase
from uuid import uuid4

from eventsourcing.domain_new import AggregateEvent
from examples.shopvertical.events import AddedProductToShop
from examples.shopvertical.exceptions import ProductAlreadyInShopError
from examples.shopvertical.slices.add_product_to_shop.cmd import AddProductToShop

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class TestAddProductToShop(TestCase):
    def test_add_product_to_shop(self) -> None:
        product_id = str(uuid4())

        product_events: Events = ()

        cmd = AddProductToShop(
            product_id=product_id,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("5.99"),
        )

        new_events = cmd.handle(product_events)
        self.assertEqual(len(new_events), 1)
        self.assertIsInstance(new_events[0].decision, AddedProductToShop)
        new_event = cast(AggregateEvent[AddedProductToShop], new_events[0])
        self.assertEqual(new_event.originator_id, product_id)
        self.assertEqual(new_event.originator_version, 1)
        self.assertEqual(new_event.decision.name, "Coffee")
        self.assertEqual(new_event.decision.description, "A very nice coffee")
        self.assertEqual(new_event.decision.price, Decimal("5.99"))

    def test_already_added_product_to_shop(self) -> None:
        product_id = str(uuid4())

        product_events: Events = (
            AggregateEvent(
                decision=AddedProductToShop(
                    name="Tea",
                    description="A very nice tea",
                    price=Decimal("5.99"),
                ),
                originator_id=product_id,
                originator_version=1,
            ),
        )

        cmd = AddProductToShop(
            product_id=product_id,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("3.99"),
        )

        with self.assertRaises(ProductAlreadyInShopError):
            cmd.handle(product_events)
