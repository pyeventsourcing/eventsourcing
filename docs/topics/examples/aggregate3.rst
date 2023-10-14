.. _Aggregate example 3:

Aggregate 3 - Explicit trigger and apply
========================================

This example shows another variation of the ``Dog`` aggregate class.

Like the previous example, this example uses the :class:`~eventsourcing.domain.Aggregate` class from the
library. Event classes are defined explicitly to match command method signatures.
In contrast to the previous example, this example explicitly triggers events within
the command method bodies, and separately applies the events to the aggregate using
an ``when()`` method decorated with ``singledispatchmethod`` with which event-specific
methods are registered. To make this work, an ``Event`` class common to all the
aggregate's events is defined, which calls the aggregate's ``apply()`` method from
its ``apply()`` method.

Like in the previous examples, the application code simply uses the aggregate
class as if it were a normal Python object class, albeit the aggregate class method
``register()`` is used to register a new dog.

Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate3/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate3/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate3/test_application.py
