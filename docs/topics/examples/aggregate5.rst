.. _Aggregate example 5:

Aggregate 5 - Immutable aggregate
=================================

This example shows the ``Dog`` class used in the tutorial and module docs.

This example also does *not* use the library ``Aggregate`` class. Instead, it
defines its own ``Aggregate`` and ``DomainEvent`` base classes. In contrast
to the previous examples, both the event and the aggregate classes are
defined as frozen dataclasses.

The ``Dog`` aggregate is a frozen dataclass, but it otherwise similar to the
previous example. It explicitly defines event classes. And it explicitly
triggers events in command methods. However, in this example the aggregate
state is evolved by constructing a new instance of the aggregate class.

In contrast to the previous examples, the application code in this example
must receive the new aggregate instance and the new domain events that are
returned from the aggregate command methods. The aggregate
projector function must also be supplied when getting an aggregate from the
repository and when taking snapshots.

Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate5/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate5/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate5/test_application.py
