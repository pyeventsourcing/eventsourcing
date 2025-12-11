========
Examples
========

This library contains a few example applications of event sourcing in Python.


.. _Example aggregates:

Example aggregates
==================

The aggregate examples show a range of different styles for coding aggregate
classes, from the declarative syntax which provides the most concise style
for expressing business concerns, to a functional style which uses immutable
aggregate objects. All these examples make use of the library's application
and persistence modules. All these examples satisfy the same test case which
involves creating and updating a ``Dog`` aggregate, and taking a snapshot.

.. toctree::
   :maxdepth: 2

   examples/aggregate1
   examples/aggregate2
   examples/aggregate3
   examples/aggregate4
   examples/aggregate5
   examples/aggregate6
   examples/aggregate7
   examples/aggregate8
   examples/aggregate9
   examples/aggregate10
   examples/aggregate11

.. _Example applications:

Example applications
====================

.. toctree::
   :maxdepth: 2

   examples/bank-accounts
   examples/cargo-shipping
   examples/content-management
   examples/searchable-timestamps
   examples/fts-content-management
   examples/shop-standard
   examples/shop-vertical

.. _Example projections:

Example projections
===================

.. toctree::
   :maxdepth: 2

   examples/fts-projection

.. _Example systems:

Example systems
===============

.. toctree::
   :maxdepth: 2

   examples/fts-process

.. _Dynamic consistency boundaries:

Dynamic consistency boundaries
==============================

.. toctree::
   :maxdepth: 2

   examples/coursebooking
   examples/coursebooking-dcb
   examples/coursebooking-dcb-postgres-tt
   examples/coursebooking-dcb-umadb
   examples/coursebooking-dcb-refactored
   examples/coursebooking-dcb-slices
