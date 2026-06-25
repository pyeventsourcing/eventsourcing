.. _Aggregate example 8:

Aggregate 8 - Pydantic mutable
==============================

This example shows how to use `Pydantic <https://pydantic.dev/docs/validation/latest/get-started>`_
with the library's :ref:`declarative syntax for mutable aggregates <Declarative syntax>`.

Similar to :doc:`example 1  </topics/examples/aggregate1>`, aggregates are expressed
using the library's declarative syntax. This is the most concise way of defining an
event-sourced aggregate.

Similar to :doc:`example 7  </topics/examples/aggregate7>`, domain event and custom value objects
are defined using Pydantic. The main advantage of using Pydantic here is that any custom value objects
used in the domain model will be automatically serialised and deserialised, without needing also to
define custom :ref:`transcoding<Transcodings>` classes.


.. _Pydantic mutable model:

Pydantic mutable model
----------------------

The library's :mod:`eventsourcing.pydantic.mutablemodel` defines base classes for aggregates that can
use the library's :ref:`declarative syntax <Declarative syntax>`.

.. literalinclude:: ../../../eventsourcing/pydantic/mutablemodel.py
    :pyobject: Aggregate

.. literalinclude:: ../../../eventsourcing/pydantic/mutablemodel.py
    :pyobject: AggregateSnapshot

.. literalinclude:: ../../../eventsourcing/pydantic/mutablemodel.py
    :pyobject: SnapshotState


Domain model
------------

The code below shows how to define a mutable aggregate with the library's declarative syntax,
using the :ref:`Pydantic mutable model`.

.. literalinclude:: ../../../examples/aggregate8/domainmodel.py


Application
-----------

The :class:`~examples.aggregate8.application.DogSchool` application in this example uses the
:ref:`Pydantic application class <Pydantic application>`.

.. literalinclude:: ../../../examples/aggregate8/application.py


Test case
---------

The :class:`~examples.aggregate8.test_application.TestDogSchool` test case shows how the
:class:`~examples.aggregate8.application.DogSchool` application can be used.

.. literalinclude:: ../../../examples/aggregate8/test_application.py


Code reference
--------------

.. automodule:: eventsourcing.pydantic.mutablemodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate8.domainmodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate8.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.aggregate8.test_application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

