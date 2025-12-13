.. _Aggregate example 10:

Aggregate 10 - msgspec with declarative syntax
==============================================

This example shows how to use msgspec with the library's declarative syntax.

Similar to :doc:`example 1  </topics/examples/aggregate1>`, aggregates are expressed
using the library's declarative syntax. This is the most concise way of defining an
event-sourced aggregate.

Similar to :doc:`example 9  </topics/examples/aggregate9>`, domain event and custom value objects
are defined using msgspec. The main advantage of using msgspec here is that any custom value objects
used in the domain model will be automatically serialised and deserialised, without needing also to
define custom :ref:`transcoding<Transcodings>` classes. The advantage of msgspec structs
over Pydantic v2 is performance.

msgspec model for mutable aggregate
-----------------------------------

The code below shows how to define base classes for mutable aggregates that use msgspec.

.. literalinclude:: ../../../examples/aggregate10/mutablemodel.py


Domain model
------------

The code below shows how to define a mutable aggregate with the library's declarative syntax, using the msgspec module for mutable aggregates

.. literalinclude:: ../../../examples/aggregate10/domainmodel.py


Application
-----------

The :class:`~examples.aggregate10.application.DogSchool` application in this example uses the
:class:`~examples.aggregate9.msgpack.MsgspecApplication` class
from :doc:`example 9 </topics/examples/aggregate9>`.

.. literalinclude:: ../../../examples/aggregate10/application.py


Test case
---------

The :class:`~examples.aggregate10.test_application.TestDogSchool` test case shows how the
:class:`~examples.aggregate10.application.DogSchool` application can be used.

.. literalinclude:: ../../../examples/aggregate10/test_application.py


Code reference
--------------

.. automodule:: examples.aggregate10.mutablemodel
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

