.. _Aggregate example 7:

Aggregate 7 - Pydantic immutable
================================

This example shows how to use `Pydantic <https://pydantic.dev/docs/validation/latest/get-started>`_
to define immutable aggregate and event classes.

The main advantage of using Pydantic is that any custom value objects
used in the domain model will be automatically serialised and deserialised,
without needing to define :ref:`custom transcoding classes<Transcodings>`.
Pydantic is also quite a lot faster at serialisation and deserialisation than
the Python Standard Library's :mod:`json` package.

This is demonstrated with the :class:`~examples.aggregate7.domainmodel.Trick` class,
which is used in both aggregate events and aggregate state, and which is reconstructed from serialised string
values, representing only the name of the trick, from both recorded aggregate events and from recorded snapshots.

.. _Pydantic immutable model:

Pydantic immutable model
------------------------

The library's :mod:`eventsourcing.pydantic.immutablemodel` module defines base classes for immutable domain events
and aggregates that use Pydantic.

.. literalinclude:: ../../../eventsourcing/pydantic/immutablemodel.py
    :pyobject: Immutable

.. literalinclude:: ../../../eventsourcing/pydantic/immutablemodel.py
    :pyobject: DomainEvent

.. literalinclude:: ../../../eventsourcing/pydantic/immutablemodel.py
    :pyobject: Aggregate

Also included is a generic function for building an immutable aggregate projector function from an immutable
aggregate mutator function.

.. literalinclude:: ../../../eventsourcing/pydantic/immutablemodel.py
    :pyobject: aggregate_projector


.. _Pydantic mapper:

Pydantic mapper
---------------

The :class:`~eventsourcing.pydantic.mapper.PydanticMapper` class is a
:ref:`mapper<Mapper>` that supports Pydantic. It is responsible for serialising and
deserialising :ref:`Pydantic immutable model` objects.

.. literalinclude:: ../../../eventsourcing/pydantic/mapper.py
    :pyobject: PydanticMapper

.. _Pydantic application:

Pydantic application
--------------------

The :class:`~eventsourcing.pydantic.application.PydanticApplication` class
is configured to use the :ref:`Pydantic mapper`. It is a subclass of the
library's :class:`~eventsourcing.application.Application` class.

.. literalinclude:: ../../../eventsourcing/pydantic/application.py
    :pyobject: PydanticApplication


Domain model
------------

The code below shows how to define an immutable :class:`~examples.aggregate7.domainmodel.Dog` aggregate in
a functional style, using the :ref:`Pydantic immutable model`.

.. literalinclude:: ../../../examples/aggregate7/domainmodel.py


Application
-----------

The :class:`~examples.aggregate7.application.DogSchool` application in this example uses the
:ref:`Pydantic application`. It must receive the new events that are returned
by the aggregate command methods, and pass them to its :func:`~eventsourcing.application.Application.save`
method. The aggregate projector function must also be supplied when reconstructing an aggregate from the
repository, and when taking snapshots.

.. literalinclude:: ../../../examples/aggregate7/application.py
    :pyobject: DogSchool


Test case
---------

The :class:`~examples.aggregate7.test_application.TestDogSchool` test case shows how the
:class:`~examples.aggregate7.application.DogSchool` application can be used.

.. literalinclude:: ../../../examples/aggregate7/test_application.py
    :pyobject: TestDogSchool


Code reference
--------------

.. automodule:: eventsourcing.pydantic.immutablemodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: eventsourcing.pydantic.mapper
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: eventsourcing.pydantic.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate7.domainmodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate7.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate7.test_application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

