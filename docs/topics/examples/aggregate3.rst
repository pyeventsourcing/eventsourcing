.. _Aggregate example 3:

Aggregate 3 - Explicit trigger and apply
========================================

This example shows the ``Dog`` class used in the tutorial and module docs.

Like the previous example, this example uses the ``Aggregate`` class from the
library. Event classes are defined explicitly to match command method signatures.
In contrast to the previous example, this example explicitly triggers events within
the command method bodies, and separately applies the events to the aggregate using
``singledispatchmethod``.

Like in the previous examples, the application code simply uses the aggregate
class as if it were a normal Python object class.

Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate3/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate3/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate3/test_application.py
