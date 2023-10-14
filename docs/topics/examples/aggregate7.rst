.. _Aggregate example 7:

Aggregate 7 - Pydantic and orjson
=================================

This example shows another variation of the ``Dog`` aggregate class used
in the tutorial and module docs.

Similar to the previous example, the model is expressed in a functional
style. In contrast to the previous example, this example uses Pydantic
to define immutable aggregate and event classes, rather than defining
them as Python frozen data classes. This has implications for the
persistence layer.

The application class in this example uses its own persistence classes
``PydanticMapper`` and ``OrjsonTranscoder``. Pydantic is responsible
for converting domain model objects to object types that orjson can
serialise, and for reconstructing model objects from JSON objects
that have been deserialised by orjson.

One advantage of using Pydantic here is that any custom value objects
will be automatically reconstructed without needing to define the
transcoding classes that would be needed when using the library's
default ``JSONTranscoder``.


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
