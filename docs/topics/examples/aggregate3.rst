.. _Aggregate example 3:

Aggregate 3 - Separate Apply Methods
====================================

This example shows the ``Dog`` class used in the tutorial and module docs.

Like the previous example, it uses the ``Aggregate`` class from the library,
and defines event classes and that are defined explicitly to match command
method signatures. In contrast from the previous example, it explicitly
triggers events within the command method bodies, and separately applies
the events to the aggregate using ``singledispatchmethod``.

Like in the previous examples, the application code simply uses the aggregate
class as if it were a normal Python object class.

Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate3/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate3/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate3/test_application.py
