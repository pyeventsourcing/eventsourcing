.. _Vertical slices example:

Application 7 - Vertical slices
===============================

This example demonstrates how to do event sourcing with the "vertical slice architecture" advocated by the event
modelling community.


Add product to shop
-------------------

.. literalinclude:: ../../../examples/shopvertical/slices/add_product_to_shop/cmd.py
    :pyobject: AddProductToShop

.. literalinclude:: ../../../examples/shopvertical/slices/add_product_to_shop/test_slice.py
    :pyobject: TestAddProductToShop

Adjust product inventory
------------------------

.. literalinclude:: ../../../examples/shopvertical/slices/adjust_product_inventory/cmd.py
    :pyobject: AdjustProductInventory

.. literalinclude:: ../../../examples/shopvertical/slices/adjust_product_inventory/test_slice.py
    :pyobject: TestAdjustProductInventory

List products in shop
---------------------

.. literalinclude:: ../../../examples/shopvertical/slices/list_products_in_shop/query.py
    :pyobject: ListProductsInShop

.. literalinclude:: ../../../examples/shopvertical/slices/list_products_in_shop/query.py
    :pyobject: ProductDetails

.. literalinclude:: ../../../examples/shopvertical/slices/list_products_in_shop/test_slice.py
    :pyobject: TestListProductsInShop

Get cart items
--------------

.. literalinclude:: ../../../examples/shopvertical/slices/get_cart_items/query.py
    :pyobject: GetCartItems

.. literalinclude:: ../../../examples/shopvertical/slices/get_cart_items/query.py
    :pyobject: CartItem

.. literalinclude:: ../../../examples/shopvertical/slices/get_cart_items/test_slice.py
    :pyobject: TestGetCartItems

Add item to cart
----------------

.. literalinclude:: ../../../examples/shopvertical/slices/add_item_to_cart/cmd.py
    :pyobject: AddItemToCart

.. literalinclude:: ../../../examples/shopvertical/slices/add_item_to_cart/test_slice.py
    :pyobject: TestAddItemToCart

Remove item from cart
---------------------

.. literalinclude:: ../../../examples/shopvertical/slices/remove_item_from_cart/cmd.py
    :pyobject: RemoveItemFromCart

.. literalinclude:: ../../../examples/shopvertical/slices/remove_item_from_cart/test_slice.py
    :pyobject: TestRemoveItemFromCart

Clear cart
----------

.. literalinclude:: ../../../examples/shopvertical/slices/clear_cart/cmd.py
    :pyobject: ClearCart

.. literalinclude:: ../../../examples/shopvertical/slices/clear_cart/test_slice.py
    :pyobject: TestClearCart

Submit cart
-----------

.. literalinclude:: ../../../examples/shopvertical/slices/submit_cart/cmd.py
    :pyobject: SubmitCart

.. literalinclude:: ../../../examples/shopvertical/slices/submit_cart/test_slice.py
    :pyobject: TestSubmitCart

Events
------

.. literalinclude:: ../../../examples/shopvertical/events.py

Exceptions
----------

.. literalinclude:: ../../../examples/shopvertical/exceptions.py

Common code
-----------

.. literalinclude:: ../../../examples/shopvertical/common.py

Integration test
----------------

.. literalinclude:: ../../../examples/shopvertical/test_shopvertical.py
    :pyobject: TestShop

Code reference
--------------

.. automodule:: examples.shopvertical.slices.add_product_to_shop.cmd
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.slices.adjust_product_inventory.cmd
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.slices.list_products_in_shop.query
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.slices.get_cart_items.query
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.slices.add_item_to_cart.cmd
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.slices.remove_item_from_cart.cmd
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.slices.clear_cart.cmd
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.slices.submit_cart.cmd
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.events
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.exceptions
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopvertical.common
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

