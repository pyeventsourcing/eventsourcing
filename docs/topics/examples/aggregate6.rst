.. _Aggregate example 6:

Aggregate 6 - Functional style
==============================

This example shows another variation of the ``Dog`` aggregate class used
in the tutorial and module docs.

Like in the previous example, this example defines immutable ``Aggregate`` and
``DomainEvent`` base classes, as frozen data classes. However, this time the
aggregate class has no methods. All the functionality has been implemented
as module-level functions.

Like in the previous examples, the application code in this example must receive
the domain events that are returned from the aggregate command methods. The aggregate
projector function must also be supplied when getting an aggregate from the
repository and when taking snapshots.


Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate6/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate6/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate6/test_application.py
