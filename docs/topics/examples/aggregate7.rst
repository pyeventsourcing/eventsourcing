.. _Aggregate example 7:

Aggregate 7 - Pydantic and orjson
=================================

This example shows the ``Dog`` class used in the tutorial and module docs.

Similar to the previous example, the model is expressed in a functional
style, and does not use the library ``Aggregate`` class.
In contrast to the previous example, the aggregate and event classes are
defined using Pydantic, rather than as Python frozen dataclasses.

The application class uses a mapper that works with Pydantic and a
transcoder that uses orjson. Pydantic is responsible for converting
model objects to object types that orjson can serialise, and
for reconstructing model objects from JSON objects deserialised
by orjson.

Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate7/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate7/application.py


Persistence
-----------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate7/persistence.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/alternative_aggregate7/test_application.py
