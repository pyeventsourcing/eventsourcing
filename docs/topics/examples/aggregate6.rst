.. _Aggregate example 6:

Aggregate 6 - Functional style
==============================

This example shows the ``Dog`` class used in the tutorial and module docs.

This example also does *not* use the library ``Aggregate`` class. Instead, it
defines its own ``Aggregate`` and ``DomainEvent`` base classes. Like in the
previous example, both the event and the aggregate classes are
defined as frozen dataclasses. However, this time the aggregate class has
no methods. All the functionality has been implemented as module-level functions.

Like in the previous examples, the application code in this example
must receive the new aggregate instance and the new domain events that are
returned from the aggregate command methods. The aggregate
projector function must also be supplied when getting an aggregate from the
repository and when taking snapshots.


Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate6/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate6/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate6/test_application.py
