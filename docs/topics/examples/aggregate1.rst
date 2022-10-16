.. _Aggregate example 1:

Aggregate 1 - Declarative syntax
================================

This example shows the ``Dog`` class used in the tutorial and module docs.

It uses the :class:`~eventsourcing.domain.Aggregate` class and the :func:`@event<eventsourcing.domain.event>` decorator from the library
to define events that are derived from command method signatures.
The bodies of the command methods are used to apply the events
to the aggregate state.

The application class simply uses the aggregate class as if it were a normal
Python object class.

Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate1/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate1/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate1/test_application.py
