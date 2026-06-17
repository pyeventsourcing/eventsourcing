import unittest
from decimal import Decimal
from typing import cast
from uuid import uuid4

from examples.shopvertical.events import AddedProductToShop, AdjustedProductInventory
from examples.shopvertical.exceptions import ProductNotFoundInShopError
from examples.shopvertical.slices.adjust_product_inventory.cmd import (
    AdjustProductInventory,
)


class TestAdjustProductInventory(unittest.TestCase):
    def test_adjust_inventory(self) -> None:
        product_id = uuid4()
        cmd = AdjustProductInventory(
            product_id=product_id,
            adjustment=2,
        )
        product_events = (
            AddedProductToShop(
                originator_id=product_id,
                originator_version=1,
                name="Tea",
                description="A very nice tea",
                price=Decimal("3.99"),
            ),
        )
        new_events = cmd.handle(product_events)
        assert len(new_events) == 1
        self.assertIsInstance(new_events[0], AdjustedProductInventory)
        new_event = cast(AdjustedProductInventory, new_events[0])
        self.assertEqual(new_event.originator_id, product_id)
        self.assertEqual(new_event.originator_version, 2)
        self.assertEqual(new_event.adjustment, 2)

    def test_adjust_inventory_product_not_found(self) -> None:
        product_id = uuid4()
        cmd = AdjustProductInventory(
            product_id=product_id,
            adjustment=2,
        )
        product_events = ()

        with self.assertRaises(ProductNotFoundInShopError):
            cmd.handle(product_events)
