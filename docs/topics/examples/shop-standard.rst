.. _Shop application example:

Application 6 - Shopping cart
=============================

This example suggests how a shopping cart might be implemented.


Application
-----------

.. literalinclude:: ../../../examples/shopstandard/application.py
    :pyobject: Shop

.. literalinclude:: ../../../examples/shopstandard/domain.py
    :pyobject: ProductDetails

Domain model
------------

.. literalinclude:: ../../../examples/shopstandard/domain.py
    :pyobject: Product

.. literalinclude:: ../../../examples/shopstandard/domain.py
    :pyobject: Cart

.. literalinclude:: ../../../examples/shopstandard/domain.py
    :pyobject: CartItem


Exceptions
----------

.. literalinclude:: ../../../examples/shopstandard/exceptions.py

Test
----

.. literalinclude:: ../../../examples/shopstandard/test_shopstandard.py
    :pyobject: TestShop

Code reference
--------------

.. automodule:: examples.shopstandard.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopstandard.domain
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__

.. automodule:: examples.shopstandard.exceptions
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
    :special-members: __init__
