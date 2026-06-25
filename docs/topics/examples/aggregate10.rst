.. _Aggregate example 10:

Aggregate 10 - msgspec with declarative syntax
==============================================

This example shows how to use `msgspec <https://msgspec.dev>`_ with the library's
:ref:`declarative syntax for mutable aggregates <Declarative syntax>`.

Similar to :doc:`example 1  </topics/examples/aggregate1>`, aggregates are expressed
using the library's declarative syntax. This is the most concise way of defining an
event-sourced aggregate.

Similar to :doc:`example 9  </topics/examples/aggregate9>`, domain event and custom value objects
are defined using msgspec. The main advantage of using msgspec here is that any custom value objects
used in the domain model will be automatically serialised and deserialised, without needing also to
define custom :ref:`transcoding<Transcodings>` classes.
Msgspec is also quite a lot faster at serialisation and deserialisation than Pydantic.


.. _Msgspec mutable model:

Msgspec mutable model
----------------------

The library's :mod:`eventsourcing.msgspec.mutablemodel` defines base classes for aggregates that can
use the library's :ref:`declarative syntax <Declarative syntax>`.

.. literalinclude:: ../../../eventsourcing/pydantic/mutablemodel.py
    :pyobject: Aggregate

.. literalinclude:: ../../../eventsourcing/pydantic/mutablemodel.py
    :pyobject: AggregateSnapshot

.. literalinclude:: ../../../eventsourcing/pydantic/mutablemodel.py
    :pyobject: SnapshotState

Domain model
------------

The code below shows how to define a mutable aggregate using the :ref:`msgspec mutable model <Msgspec mutable model>`.

.. literalinclude:: ../../../examples/aggregate10/domainmodel.py


Application
-----------

The :class:`~examples.aggregate10.application.DogSchool` application in this example uses the
library's :ref:`msgspec application class <Msgspec application>`.

.. literalinclude:: ../../../examples/aggregate10/application.py


Test case
---------

The :class:`~examples.aggregate10.test_application.TestDogSchool` test case shows how the
:class:`~examples.aggregate10.application.DogSchool` application can be used.

.. literalinclude:: ../../../examples/aggregate10/test_application.py


Code reference
--------------

.. automodule:: eventsourcing.msgspec.mutablemodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate10.domainmodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate10.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate10.test_application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

