.. _Aggregate example 8:

Aggregate 8 - Pydantic with declarative syntax
==============================================

This example shows the ``Dog`` class used in the tutorial and module docs.

Similar to the first example, the aggregate is expressed using the library's
declarative syntax. And similar to the previous example, the model events
are defined using Pydantic. To show both cases, one event is defined
implicitly from the method signature, and another event is defined
explicitly and referenced in the command method decorator.

Similar to the previous example, the application class in this example
uses the persistence classes ``PydanticMapper`` and ``OrjsonTranscoder``.
Pydantic is responsible for converting domain model objects to object types
that orjson can serialise, and for reconstructing model objects from JSON
objects that have been deserialised by orjson. The application class also
uses the custom ``Snapshot`` class, which is defined as a Pydantic
model.


Domain model
------------

.. literalinclude:: ../../../eventsourcing/examples/aggregate8/domainmodel.py


Application
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate8/application.py


Persistence
-----------


.. literalinclude:: ../../../eventsourcing/examples/aggregate8/persistence.py


Test case
---------


.. literalinclude:: ../../../eventsourcing/examples/aggregate8/test_application.py
