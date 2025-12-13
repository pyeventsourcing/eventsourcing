.. _Aggregate example 9:

Aggregate 9 - msgspec structs
=============================

This example shows how to use msgspec structs to define immutable aggregate and event classes.

Like with Pydantic, the main advantage of using msgspec here is that any custom value objects
used in the domain model will be automatically serialised and deserialised, without needing
also to define custom :ref:`transcoding<Transcodings>` classes. This is demonstrated in the
example below with the :class:`~examples.aggregate9.domainmodel.Trick` class, which is used
in both aggregate events and aggregate state, and which is reconstructed from serialised string
values, representing only the name of the trick, from both recorded aggregate events and from
recorded snapshots.

The advantage of msgspec structs over Pydantic v2 is performance. The tables below show relative
performance of msgspec, Pydantic v2, and the Python Standard Library for mapping between
:ref:`domain events <Domain events>` and :ref:`stored events <Stored event objects>`.
The benchmarks were done with pytest-benchmark.

.. list-table:: Encoding domain events to stored events
   :widths: 30 30 30
   :header-rows: 1

   * - Name
     - Encode time (ns)
     - OPS (Kops/s)
   * - msgspec
     - 1121 (1.0x)
     - 862 (1.0x)
   * - pydantic
     - 2688 (2.40x)
     - 352 (0.41x)
   * - json
     - 5083 (4.54x)
     - 184 (0.21x)

.. list-table:: Decoding stored events to domain events
   :widths: 30 30 30
   :header-rows: 1

   * - Name
     - Decode time (ns)
     - OPS (Kops/s)
   * - msgspec
     - 679 (1.0x)
     - 1416 (1.0x)
   * - pydantic
     - 2750 (4.05x)
     - 346 (0.24x)
   * - json
     - 3208 (4.72x)
     - 296 (0.21x)


MessagePack mapper
------------------

The :class:`~examples.aggregate9.msgpack.MessagePackMapper` class is a :ref:`mapper<Mapper>` that supports
msgspec structs. It is responsible for converting domain model objects to Python bytes objects, and for
reconstructing model objects from Python bytes objects.

.. literalinclude:: ../../../examples/aggregate9/msgpack.py
    :pyobject: MessagePackMapper

The :class:`~examples.aggregate9.msgpack.MsgspecApplication` class is a
subclass of the library's :class:`~eventsourcing.application.Application` class
which is configured to use :class:`~examples.aggregate9.msgpack.MessagePackMapper`.

.. literalinclude:: ../../../examples/aggregate9/msgpack.py
    :pyobject: MsgspecApplication


Msgspec model for immutable aggregate
-------------------------------------

The code below shows how to define base classes for immutable aggregates that use msgspec structs.

.. literalinclude:: ../../../examples/aggregate9/immutablemodel.py


Domain model
------------

The code below shows how to define an immutable aggregate in a functional style, using the msgspec module for immutable aggregates

.. literalinclude:: ../../../examples/aggregate9/domainmodel.py


Application
-----------

The :class:`~examples.aggregate9.application.DogSchool` application in this example uses the
:class:`~examples.aggregate9.msgpack.MsgspecApplication`. It must receive the new events that are returned
by the aggregate command methods, and pass them to its :func:`~eventsourcing.application.Application.save`
method. The aggregate projector function must also be supplied when reconstructing an aggregate from the
repository, and when taking snapshots.

.. literalinclude:: ../../../examples/aggregate9/application.py
    :pyobject: DogSchool


Test case
---------

The :class:`~examples.aggregate9.test_application.TestDogSchool` test case shows how the
:class:`~examples.aggregate9.application.DogSchool` application can be used.

.. literalinclude:: ../../../examples/aggregate9/test_application.py
    :pyobject: TestDogSchool


Code reference
--------------

.. automodule:: examples.aggregate9.immutablemodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate9.msgpack
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate9.domainmodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate9.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate9.test_application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:
