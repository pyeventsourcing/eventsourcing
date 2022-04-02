========
Examples
========

This library contains a few example applications of event sourcing in Python.


Aggregate examples
==================

The aggregate examples show a range of different styles for coding aggregate
classes, from the declarative syntax which provides the most concise style
for expressing business concerns, to a functional style which uses immutable
aggregate objects. All these examples make use of the library's application
and persistence modules. All these examples satisfy the same test case which
involves creating and updating a `Dog` aggregate, and taking a snapshot.


.. toctree::
   :maxdepth: 2

   examples/aggregate1
   examples/aggregate2
   examples/aggregate3
   examples/aggregate4
   examples/aggregate5
   examples/aggregate6


Example applications
====================

.. toctree::
   :maxdepth: 2

   examples/bank-accounts
   examples/cargo-shipping
   examples/wiki
