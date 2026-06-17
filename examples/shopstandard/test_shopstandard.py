from __future__ import annotations

from decimal import Decimal
from unittest import TestCase
from uuid import UUID, uuid4

from examples.shopstandard.application import Shop
from examples.shopstandard.exceptions import (
    CartAlreadySubmittedError,
    CartFullError,
    InsufficientInventoryError,
    ProductAlreadyInShopError,
    ProductNotFoundInShopError,
    ProductNotInCartError,
)


class TestShop(TestCase):
    def test(self) -> None:
        app = Shop()

        product_id1: UUID = uuid4()
        product_id2: UUID = uuid4()
        product_id3: UUID = uuid4()
        product_id4: UUID = uuid4()
        product_id5: UUID = uuid4()

        # Add products to shop.
        app.add_product_to_shop(
            product_id=product_id1,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("5.99"),
        )

        with self.assertRaises(ProductAlreadyInShopError):
            app.add_product_to_shop(
                product_id=product_id1,
                name="Coffee",
                description="A very nice coffee",
                price=Decimal("5.99"),
            )

        app.add_product_to_shop(
            product_id=product_id2,
            name="Tea",
            description="A very nice tea",
            price=Decimal("3.99"),
        )

        # Adjust product inventory.
        app.adjust_product_inventory(
            product_id=product_id1,
            adjustment=3,
        )

        # Product not in shop.
        with self.assertRaises(ProductNotFoundInShopError):
            app.adjust_product_inventory(
                product_id=product_id3,
                adjustment=1,
            )

        app.add_product_to_shop(
            product_id=product_id3,
            name="Sugar",
            description="A very nice sugar",
            price=Decimal("2.99"),
        )

        app.add_product_to_shop(
            product_id=product_id4,
            name="Milk",
            description="A very nice milk",
            price=Decimal("1.99"),
        )

        # List products.
        products = app.list_products_in_shop()
        self.assertEqual(len(products), 4)
        self.assertEqual(products[0].id, product_id1)
        self.assertEqual(products[0].name, "Coffee")
        self.assertEqual(products[0].description, "A very nice coffee")
        self.assertEqual(products[0].price, Decimal("5.99"))
        self.assertEqual(products[0].inventory, 3)
        self.assertEqual(products[1].id, product_id2)
        self.assertEqual(products[1].name, "Tea")
        self.assertEqual(products[1].description, "A very nice tea")
        self.assertEqual(products[1].price, Decimal("3.99"))
        self.assertEqual(products[1].inventory, 0)
        self.assertEqual(products[2].id, product_id3)
        self.assertEqual(products[2].name, "Sugar")
        self.assertEqual(products[2].description, "A very nice sugar")
        self.assertEqual(products[2].price, Decimal("2.99"))
        self.assertEqual(products[2].inventory, 0)
        self.assertEqual(products[3].id, product_id4)
        self.assertEqual(products[3].name, "Milk")
        self.assertEqual(products[3].description, "A very nice milk")
        self.assertEqual(products[3].price, Decimal("1.99"))
        self.assertEqual(products[3].inventory, 0)

        # Get cart items - should be 0.
        cart_id = uuid4()
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 0)

        # Add item to cart.
        app.add_item_to_cart(
            cart_id=cart_id,
            product_id=product_id1,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("5.99"),
        )

        # Get cart items - should be 1.
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 1)

        # Check everything is getting serialised and deserialised correctly.
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[0].name, "Coffee")
        self.assertEqual(cart_items[0].description, "A very nice coffee")
        self.assertEqual(cart_items[0].price, Decimal("5.99"))

        # Clear cart.
        app.clear_cart(cart_id)

        # Get cart items - should be 0.
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 0)

        # Add item to cart.
        app.add_item_to_cart(
            cart_id=cart_id,
            product_id=product_id1,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("5.99"),
        )

        # Add item to cart.
        app.add_item_to_cart(
            cart_id=cart_id,
            product_id=product_id2,
            name="Tea",
            description="A very nice tea",
            price=Decimal("3.99"),
        )

        # Get cart items - should be 2.
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 2)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id2)

        # Add item to cart.
        app.add_item_to_cart(
            cart_id=cart_id,
            product_id=product_id3,
            name="Sugar",
            description="A very nice sugar",
            price=Decimal("2.99"),
        )

        # Get cart items - should be 3.
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 3)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id2)
        self.assertEqual(cart_items[2].product_id, product_id3)

        # Cart full error.
        with self.assertRaises(CartFullError):
            app.add_item_to_cart(
                cart_id=cart_id,
                product_id=product_id4,
                name="Milk",
                description="A very nice milk",
                price=Decimal("1.99"),
            )

        # Get cart items - should be 3.
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 3)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id2)
        self.assertEqual(cart_items[2].product_id, product_id3)

        # Remove item from cart.
        app.remove_item_from_cart(
            cart_id=cart_id,
            product_id=product_id2,
        )

        # Get cart items - should be 2.
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 2)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id3)

        # Product not in cart error.
        with self.assertRaises(ProductNotInCartError):
            app.remove_item_from_cart(
                cart_id=cart_id,
                product_id=product_id2,
            )

        # Add item to cart.
        app.add_item_to_cart(
            cart_id=cart_id,
            product_id=product_id5,
            name="Spoon",
            description="A very nice spoon",
            price=Decimal("0.99"),
        )

        # Get cart items - should be 3.
        cart_items = app.get_cart_items(cart_id)
        self.assertEqual(len(cart_items), 3)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id3)
        self.assertEqual(cart_items[2].product_id, product_id5)

        # Insufficient inventory error.
        with self.assertRaises(InsufficientInventoryError):
            app.submit_cart(cart_id)

        # Adjust product inventory.
        app.adjust_product_inventory(
            product_id=product_id3,
            adjustment=3,
        )

        # Insufficient inventory error.
        with self.assertRaises(InsufficientInventoryError):
            app.submit_cart(cart_id)

        # Add item to shop.
        app.add_product_to_shop(
            product_id=product_id5,
            name="Spoon",
            description="A very nice spoon",
            price=Decimal("0.99"),
        )

        # Adjust product inventory.
        app.adjust_product_inventory(
            product_id=product_id5,
            adjustment=3,
        )

        # Submit cart.
        app.submit_cart(cart_id)

        # Cart already submitted.
        with self.assertRaises(CartAlreadySubmittedError):
            app.add_item_to_cart(
                cart_id=cart_id,
                product_id=product_id4,
                name="Milk",
                description="A very nice milk",
                price=Decimal("1.99"),
            )

        with self.assertRaises(CartAlreadySubmittedError):
            app.remove_item_from_cart(
                cart_id=cart_id,
                product_id=product_id1,
            )

        with self.assertRaises(CartAlreadySubmittedError):
            app.clear_cart(
                cart_id=cart_id,
            )

        with self.assertRaises(CartAlreadySubmittedError):
            app.submit_cart(
                cart_id=cart_id,
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
