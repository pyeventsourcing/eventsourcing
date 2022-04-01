.. _Aggregate example 1:

Aggregate example 1
===================

This example shows the ``Dog`` class used in the tutorial and module docs.

It uses the ``Aggregate`` class and the ``@event`` decorator from the library
to define events that are derived from command method signatures.
The bodies of the command methods are used to apply the events
to the aggregate state.

The application code simply uses the aggregate class as if it were a normal
Python object class.

Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate1/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate1/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate1/test_application.py
