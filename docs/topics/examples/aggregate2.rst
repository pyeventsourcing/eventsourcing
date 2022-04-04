.. _Aggregate example 2:

Aggregate 2 - Explicit event classes
====================================

This example shows the ``Dog`` class used in the tutorial and module docs.

It uses the ``Aggregate`` class and the ``@event`` decorator from the library
to use event classes that are defined explicitly to match command method
signatures. The bodies of the command methods are used to apply the events
to the aggregate state.

As in the previous example, the application code simply uses the aggregate
class as if it were a normal Python object class.


Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate2/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate2/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate2/test_application.py
