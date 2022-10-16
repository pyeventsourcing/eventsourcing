.. _Aggregate example 2:

Aggregate 2 - Explicit event classes
====================================

This example shows a slightly different version of the ``Dog`` class used in the
tutorial and module docs.

It uses the :class:`~eventsourcing.domain.Aggregate` class and the :func:`@event<eventsourcing.domain.event>` decorator from the library,
but explicitly defines event classes to match command method signatures. As in
the previous example, the event are triggered when the command methods are called,
and the bodies of the command methods are used to apply the events to the aggregate
state.

As in the previous example, the application code simply uses the aggregate
class as if it were a normal Python object class.


Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate2/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate2/application.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate2/test_application.py
