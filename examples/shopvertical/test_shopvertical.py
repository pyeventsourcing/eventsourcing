from __future__ import annotations

from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from examples.shopvertical.common import reset_application
from examples.shopvertical.exceptions import (
    CartAlreadySubmittedError,
    CartFullError,
    InsufficientInventoryError,
    ProductAlreadyInShopError,
    ProductNotFoundInShopError,
    ProductNotInCartError,
)
from examples.shopvertical.slices.add_item_to_cart.cmd import (
    AddItemToCart,
)
from examples.shopvertical.slices.add_product_to_shop.cmd import AddProductToShop
from examples.shopvertical.slices.adjust_product_inventory.cmd import (
    AdjustProductInventory,
)
from examples.shopvertical.slices.clear_cart.cmd import (
    ClearCart,
)
from examples.shopvertical.slices.get_cart_items.query import GetCartItems
from examples.shopvertical.slices.list_products_in_shop.query import ListProductsInShop
from examples.shopvertical.slices.remove_item_from_cart.cmd import (
    RemoveItemFromCart,
)
from examples.shopvertical.slices.submit_cart.cmd import (
    SubmitCart,
)


class TestShop(TestCase):
    def setUp(self) -> None:
        reset_application()

    def test(self) -> None:
        product_id1 = uuid4()
        product_id2 = uuid4()
        product_id3 = uuid4()
        product_id4 = uuid4()
        product_id5 = uuid4()

        # Add products to shop.
        AddProductToShop(
            product_id=product_id1,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("5.99"),
        ).execute()

        with self.assertRaises(ProductAlreadyInShopError):
            AddProductToShop(
                product_id=product_id1,
                name="Coffee",
                description="A very nice coffee",
                price=Decimal("5.99"),
            ).execute()

        AddProductToShop(
            product_id=product_id2,
            name="Tea",
            description="A very nice tea",
            price=Decimal("3.99"),
        ).execute()

        # Adjust product inventory.
        AdjustProductInventory(
            product_id=product_id1,
            adjustment=3,
        ).execute()

        # Product not in shop.
        with self.assertRaises(ProductNotFoundInShopError):
            AdjustProductInventory(
                product_id=product_id3,
                adjustment=1,
            ).execute()

        AddProductToShop(
            product_id=product_id3,
            name="Sugar",
            description="A very nice sugar",
            price=Decimal("2.99"),
        ).execute()

        AddProductToShop(
            product_id=product_id4,
            name="Milk",
            description="A very nice milk",
            price=Decimal("1.99"),
        ).execute()

        # List products.
        products = ListProductsInShop().execute()
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
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 0)

        # Add item to cart.
        AddItemToCart(
            cart_id=cart_id,
            product_id=product_id1,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("5.99"),
        ).execute()

        # Get cart items - should be 1.
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 1)

        # Check everything is getting serialised and deserialised correctly.
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[0].name, "Coffee")
        self.assertEqual(cart_items[0].description, "A very nice coffee")
        self.assertEqual(cart_items[0].price, Decimal("5.99"))

        # Clear cart.
        ClearCart(cart_id=cart_id).execute()

        # Get cart items - should be 0.
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 0)

        # Add item to cart.
        AddItemToCart(
            cart_id=cart_id,
            product_id=product_id1,
            name="Coffee",
            description="A very nice coffee",
            price=Decimal("5.99"),
        ).execute()

        # Add item to cart.
        AddItemToCart(
            cart_id=cart_id,
            product_id=product_id2,
            name="Tea",
            description="A very nice tea",
            price=Decimal("3.99"),
        ).execute()

        # Get cart items - should be 2.
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 2)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id2)

        # Add item to cart.
        AddItemToCart(
            cart_id=cart_id,
            product_id=product_id3,
            name="Sugar",
            description="A very nice sugar",
            price=Decimal("2.99"),
        ).execute()

        # Get cart items - should be 3.
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 3)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id2)
        self.assertEqual(cart_items[2].product_id, product_id3)

        # Cart full error.
        with self.assertRaises(CartFullError):
            AddItemToCart(
                cart_id=cart_id,
                product_id=product_id4,
                name="Milk",
                description="A very nice milk",
                price=Decimal("1.99"),
            ).execute()

        # Get cart items - should be 3.
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 3)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id2)
        self.assertEqual(cart_items[2].product_id, product_id3)

        # Remove item from cart.
        RemoveItemFromCart(
            cart_id=cart_id,
            product_id=product_id2,
        ).execute()

        # Get cart items - should be 2.
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 2)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id3)

        # Product not in cart error.
        with self.assertRaises(ProductNotInCartError):
            RemoveItemFromCart(
                cart_id=cart_id,
                product_id=product_id2,
            ).execute()

        # Add item to cart.
        AddItemToCart(
            cart_id=cart_id,
            product_id=product_id5,
            name="Spoon",
            description="A very nice spoon",
            price=Decimal("5.99"),
        ).execute()

        # Get cart items - should be 3.
        cart_items = GetCartItems(cart_id=cart_id).execute()
        self.assertEqual(len(cart_items), 3)
        self.assertEqual(cart_items[0].product_id, product_id1)
        self.assertEqual(cart_items[1].product_id, product_id3)
        self.assertEqual(cart_items[2].product_id, product_id5)

        # Insufficient inventory error.
        with self.assertRaises(InsufficientInventoryError):
            SubmitCart(cart_id=cart_id).execute()

        # Adjust product inventory.
        AdjustProductInventory(
            product_id=product_id3,
            adjustment=3,
        ).execute()

        # Insufficient inventory error.
        with self.assertRaises(InsufficientInventoryError):
            SubmitCart(cart_id=cart_id).execute()

        # Add item to shop.
        AddProductToShop(
            product_id=product_id5,
            name="Spoon",
            description="A very nice spoon",
            price=Decimal("0.99"),
        ).execute()

        # Adjust product inventory.
        AdjustProductInventory(
            product_id=product_id5,
            adjustment=3,
        ).execute()

        # Submit cart.
        SubmitCart(cart_id=cart_id).execute()

        # Cart already submitted.
        with self.assertRaises(CartAlreadySubmittedError):
            AddItemToCart(
                cart_id=cart_id,
                product_id=product_id4,
                name="Milk",
                description="A very nice milk",
                price=Decimal("1.99"),
            ).execute()

        with self.assertRaises(CartAlreadySubmittedError):
            RemoveItemFromCart(
                cart_id=cart_id,
                product_id=product_id1,
            ).execute()

        with self.assertRaises(CartAlreadySubmittedError):
            ClearCart(
                cart_id=cart_id,
            ).execute()

        with self.assertRaises(CartAlreadySubmittedError):
            SubmitCart(
                cart_id=cart_id,
            ).execute()
