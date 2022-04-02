.. _Aggregate example 4:

Aggregate 4 - Custom Base Classes
=================================

This example shows the ``Dog`` class used in the tutorial and module docs.

In contrast with the previous examples, this example does *not* use the
library ``Aggregate`` class. Instead, it defines its own ``Aggregate`` and
``DomainEvent`` base classes. Similar to the previous examples, the ``Aggregate``
class is a normal (mutable) Python class and the ``DomainEvent`` class is a
frozen Python dataclass.

The aggregate event classes are explicitly defined, and the command method
bodies explicitly trigger events. Like the previous example, this example uses
a separate function to apply events to mutate the aggregate state.

As in the previous example, the application code simply uses the aggregate
class as if it were a normal Python object class. However, the aggregate
projector function must be supplied when getting an aggregate from the
repository and when taking snapshots.


Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate4/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate4/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate4/test_application.py
