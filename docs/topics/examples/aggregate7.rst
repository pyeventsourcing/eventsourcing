.. _Aggregate example 7:

Aggregate 7 - Pydantic and orjson
=================================

This example shows the ``Dog`` class used in the tutorial and module docs.

Similar to the previous example, the model is expressed in a functional
style, and does not use the library ``Aggregate`` class.
In contrast to the previous example, the aggregate and event classes are
defined as Pydantic immutable models, rather than as Python frozen dataclasses.

The application class in this example uses the persistence classes
``PydanticMapper`` and ``OrjsonTranscoder``. Pydantic is responsible
for converting domain model objects to object types that orjson can
serialise, and for reconstructing model objects from JSON objects
that have been deserialised by orjson. The application class also
uses the custom ``Snapshot`` class, which is defined as a Pydantic
model.


Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate7/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate7/application.py


Persistence
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate7/persistence.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate7/test_application.py
